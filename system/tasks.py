import difflib
import gc
import os
import shutil
import subprocess
import time
import zipfile
# from time import sleep

import numpy as np
import sqlalchemy
from PIL import Image
from PyQt5.QtCore import (QObject, QRunnable, QThread, QThreadPool, QTimer,
                          pyqtSignal)
from PyQt5.QtGui import QImage
from PyQt5.QtTest import QTest
from sqlalchemy.exc import IntegrityError, OperationalError
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers.polling import PollingObserver as Observer

from cfg import JsonData, Static
from system.shared_utils import PathFinder, ReadImage, SharedUtils

from .database import CACHE, Clmns, Dbase
from .items import BaseItem, CopyItem, MainWinItem, SearchItem, SortItem
from .utils import Utils


class URunnable(QRunnable):
    def __init__(self):
        """
        Переопределите метод task().
        Не переопределяйте run().
        """
        super().__init__()
        self.should_run__ = True
        self.finished__ = False

    def is_should_run(self):
        return self.should_run__
    
    def set_should_run(self, value: bool):
        self.should_run__ = value

    def set_finished(self, value: bool):
        self.finished__ = value

    def is_finished(self):
        return self.finished__
    
    def run(self):
        try:
            self.task()
        finally:
            self.set_finished(True)
            if self in UThreadPool.tasks:
                QTimer.singleShot(5000, lambda: self.task_fin())

    def task(self):
        raise NotImplementedError("Переопредели метод task() в подклассе.")
    
    def task_fin(self):
        UThreadPool.tasks.remove(self)
        gc.collect()


class UThreadPool:
    pool: QThreadPool = None
    tasks: list[URunnable] = []

    @classmethod
    def init(cls):
        cls.pool = QThreadPool.globalInstance()

    @classmethod
    def start(cls, runnable: QRunnable):
        # cls.tasks.append(runnable)
        cls.pool.start(runnable)


class ActionsTask(URunnable):
    def __init__(self,  cmd_: callable):
        super().__init__()
        self.cmd_ = cmd_

    def task(self):
        self.cmd_()


class CopyFilesTask(URunnable):

    class Sigs(QObject):
        finished_ = pyqtSignal(list)
        file_count = pyqtSignal(tuple)
        copied_size = pyqtSignal(int)
        total_size = pyqtSignal(int)
        error_win = pyqtSignal()
        replace_files_win = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.sigs = CopyFilesTask.Sigs()
        self.pause_flag = False
        self.paths: list[str] = []
        self.src_dest_list: list[tuple[str, str]] = []
        self.copied_size = 0

    def prepare_same_dir(self):
        """
        Если файлы и папки скопированы в одной директории и будут вставлены туда же,
        то они будут вставлены с припиской "копия"
        """
        for src_url in CopyItem.urls:
            if os.path.isfile(src_url):
                new_filename = self.add_copy_to_name(src_url)
                self.src_dest_list.append((src_url, new_filename))
                self.paths.append(new_filename)
            else:
                new_dir_name = self.add_copy_to_name(src_url)
                # получаем все url файлов для папки
                # заменяем имя старой папки на имя новой папки
                nested_urls = [
                    (x, x.replace(src_url, new_dir_name))
                    for x in self.get_nested_urls(src_url)
                ]
                self.src_dest_list.extend(nested_urls)
                self.paths.append(new_dir_name)
    
    def prepare_another_dir(self):
        """
        Подготовка к простому копированию из одного места в другое.
        При этом может выскочить окно о замене файлов, и если 
        пользователь не согласится заменить файлы, задача копирования будет
        отменена.
        """
        for src_url in CopyItem.urls:
            if os.path.isfile(src_url):
                new_filename = src_url.replace(CopyItem.get_src(), CopyItem.get_dest())
                self.src_dest_list.append((src_url, new_filename))
                self.paths.append(new_filename)
            else:
                new_dir_name = src_url.replace(CopyItem.get_src(), CopyItem.get_dest())
                # получаем все url файлов для папки
                # заменяем имя старой папки на имя новой папки
                nested_urls = [
                    (x, x.replace(CopyItem.get_src(), CopyItem.get_dest()))
                    for x in self.get_nested_urls(src_url)
                ]
                self.src_dest_list.extend(nested_urls)
                self.paths.append(new_dir_name)

        for src, dest in self.src_dest_list:
            if os.path.exists(dest):
                self.sigs.replace_files_win.emit()
                self.pause_flag = True
                while self.pause_flag:
                    QThread.msleep(100)
                break

    def prepare_search_dir(self):
        existing_paths = set()

        for url in CopyItem.urls:
            filename = os.path.basename(url)
            dest_dir = CopyItem.get_dest()
            base_name, ext = os.path.splitext(filename)

            new_name = filename
            count = 2
            full_path = os.path.join(dest_dir, new_name)

            while full_path in existing_paths:
                new_name = f"{base_name} {count}{ext}"
                full_path = os.path.join(dest_dir, new_name)
                count += 1

            existing_paths.add(full_path)
            self.src_dest_list.append((url, full_path))
            self.paths.append(full_path)

    def task(self):
        if CopyItem.get_is_search():
            self.prepare_search_dir()
        elif CopyItem.get_src() == CopyItem.get_dest():
            self.prepare_same_dir()
        else:
            self.prepare_another_dir()

        total_size = 0
        for src, dest in self.src_dest_list:
            total_size += os.path.getsize(src)

        self.sigs.total_size.emit(total_size)

        for count, (src, dest) in enumerate(self.src_dest_list, start=1):
            if not self.is_should_run():
                break
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            self.sigs.file_count.emit((count, len(self.src_dest_list)))
            try:
                self.copy_file_with_progress(src, dest)
            except Exception as e:
                Utils.print_error()
                self.sigs.error_win.emit()
                break
            if CopyItem.get_is_cut() and not CopyItem.get_is_search():
                os.remove(src)

        if CopyItem.get_is_cut() and not CopyItem.get_is_search():
            for i in CopyItem.urls:
                if os.path.isdir(i):
                    shutil.rmtree(i)

        self.sigs.finished_.emit(self.paths)

    def add_copy_to_name(self, url: str):
        dir_name, file_name = os.path.split(url)
        name, ext = os.path.splitext(file_name)
        new_name = f"{name} копия{ext}"
        return os.path.join(dir_name, new_name)

    def get_nested_urls(self, src_dir: str):
        stack = [src_dir]
        nested_paths: list[str] = []
        while stack:
            current_dir = stack.pop()
            for dir_entry in os.scandir(current_dir):
                if dir_entry.is_dir():
                    stack.append(dir_entry.path)
                else:
                    nested_paths.append(dir_entry.path)
        return nested_paths
    
    def copy_file_with_progress(self, src, dest):
        block = 4 * 1024 * 1024  # 4 MB
        with open(src, "rb") as fsrc, open(dest, "wb") as fdst:
            shutil.copystat(src, dest, follow_symlinks=True)  # если нужны метаданные
            while True:
                buf = fsrc.read(block)
                if not buf:
                    break
                fdst.write(buf)
                self.copied_size += len(buf)
                self.sigs.copied_size.emit(self.copied_size)

                while self.pause_flag:
                    QThread.msleep(100)

        shutil.copystat(src, dest, follow_symlinks=True)


class RatingTask(URunnable):

    class Sigs(QObject):
        finished_ = pyqtSignal()

    def __init__(self, main_dir: str, base_item: BaseItem, new_rating: int):
        super().__init__()
        self.base_item = base_item
        self.new_rating = new_rating
        self.main_dir = main_dir
        self.sigs = RatingTask.Sigs()

    def task(self):        
        conn = Dbase.get_conn(Dbase.engine)
        stmt = sqlalchemy.update(CACHE)
        if self.base_item.type_ == Static.folder_type:
            stmt = stmt.where(*BaseItem.get_folder_conds(self.base_item))
        else:
            stmt = stmt.where(Clmns.partial_hash==self.base_item.partial_hash)
        stmt = stmt.values(rating=self.new_rating)
        Dbase.execute(conn, stmt)
        Dbase.commit(conn)
        Dbase.close_conn(conn)
        self.sigs.finished_.emit()


class SearchTask(URunnable):

    class Sigs(QObject):
        new_widget = pyqtSignal(BaseItem)
        finished_ = pyqtSignal(list)

    sleep_ms = 1000
    new_wid_sleep_ms = 200
    ratio = 0.85

    def __init__(self, main_win_item: MainWinItem, search_item: SearchItem):
        super().__init__()
        self.sigs = SearchTask.Sigs()
        self.main_win_item = main_win_item
        self.found_files_list: list[str] = []

        self.search_item = search_item
        self.files_list_lower: list[str] = []
        self.text_lower: str = None
        self.exts_lower: tuple[str] = None

        self.db_path: str = None
        self.pause = False
        self.insert_count = 0

        self.conn = Dbase.get_conn(Dbase.engine)

    def task(self):
        self.setup_search()
        self.scandir_recursive()
        missed_files_list: list[str] = []
        if isinstance(self.search_item.get_content(), list):
            if self.is_should_run():
                no_ext_list = [
                    os.path.splitext(i)[0]
                    for i in self.search_item.get_content()
                ]
                for i in no_ext_list:
                    if i not in self.found_files_list:
                        missed_files_list.append(i)
        self.sigs.finished_.emit(missed_files_list)
        Dbase.close_conn(self.conn)

    def setup_search(self):
        if isinstance(self.search_item.get_content(), list):
            if self.search_item.get_filter() == 0:
                self.process_entry = self.process_list_free
            elif self.search_item.get_filter() == 1:
                self.process_entry = self.process_list_exactly
            else:
                self.process_entry = self.process_list_contains

            for i in self.search_item.get_content():
                filename, _ = self.remove_extension(i)
                self.files_list_lower.append(filename.lower())

        elif isinstance(self.search_item.get_content(), tuple):
            self.process_entry = self.process_extensions
            exts_lower = (i.lower() for i in self.search_item.get_content())
            self.exts_lower = tuple(exts_lower)

        elif isinstance(self.search_item.get_content(), str):
            if self.search_item.get_filter() == 0:
                self.process_entry = self.process_text_free
            elif self.search_item.get_filter() == 1:
                self.process_entry = self.process_text_exactly
            else:
                self.process_entry = self.process_text_contains

            self.text_lower = self.search_item.get_content().lower()
    
    def remove_extension(self, filename: str):
        return os.path.splitext(filename)
        
    # базовый метод обработки os.DirEntry
    def process_entry(self, entry: os.DirEntry): ...

    def process_extensions(self, entry: os.DirEntry):
        path = entry.path
        path: str = path.lower()
        if path.endswith(self.exts_lower):
            return True
        else:
            return False

    def process_text_free(self, entry: os.DirEntry):
        filename, _ = self.remove_extension(entry.name)
        filename: str = filename.lower()
        if self.similarity_ratio(self.text_lower, filename) > SearchTask.ratio:
            return True
        else:
            return False
        
    def process_text_exactly(self, entry: os.DirEntry):
        filename, _ = self.remove_extension(entry.name)
        filename: str = filename.lower()
        if filename == self.text_lower:
            return True
        else:
            return False

    def process_text_contains(self, entry: os.DirEntry):
        filename, _ = self.remove_extension(entry.name)
        filename: str = filename.lower()
        if self.text_lower in filename:
            return True
        else:
            return False

    def process_list_exactly(self, entry: os.DirEntry):
        true_filename, _ = self.remove_extension(entry.name)
        filename: str = true_filename.lower()
        for item in self.files_list_lower:
            if filename == item:
                self.found_files_list.append(true_filename)
                return True
        return False

    def process_list_free(self, entry: os.DirEntry):
        true_filename, _ = self.remove_extension(entry.name)
        filename: str = true_filename.lower()
        for item in self.files_list_lower:
            if self.similarity_ratio(item, filename) > SearchTask.ratio:
                self.found_files_list.append(true_filename)
                return True
        return False

    def process_list_contains(self, entry: os.DirEntry):
        true_filename, _ = self.remove_extension(entry.name)
        filename: str = true_filename.lower()
        for item in self.files_list_lower:
            if item in filename:
                self.found_files_list.append(true_filename)
                return True
        return False

    def similarity_ratio(self, a: str, b: str) -> float:
        return difflib.SequenceMatcher(None, a, b).ratio()

    def scandir_recursive(self):
        # Инициализируем список с корневым каталогом
        dirs_list = [self.main_win_item.main_dir]
        while dirs_list:
            current_dir = dirs_list.pop()
            while self.pause:
                QTest.qSleep(SearchTask.sleep_ms)
                if not self.is_should_run():
                    return
            if not self.is_should_run():
                return
            if not os.path.exists(current_dir):
                continue
            try:
                # Сканируем текущий каталог и добавляем новые пути в стек
                self.scan_current_dir(current_dir, dirs_list)
            except OSError as e:
                Utils.print_error()
                continue
            except Exception as e:
                Utils.print_error()
                continue

    def scan_current_dir(self, dir: str, dirs_list: list):
        for entry in os.scandir(dir):
            while self.pause:
                QTest.qSleep(SearchTask.sleep_ms)
                if not self.is_should_run():
                    return
            if not self.is_should_run():
                return
            if entry.name.startswith(Static.hidden_symbols):
                continue
            if entry.is_dir():
                dirs_list.append(entry.path)
                # continue
            if self.process_entry(entry):
                self.process_img(entry)

    def process_img(self, entry: os.DirEntry):

        def execute_stmt_list(stmt_list: list):
            for i in stmt_list:
                Dbase.execute(self.conn, i)
            Dbase.commit(self.conn)

        def insert(base_item: BaseItem, img_array: np.ndarray):
            if Utils.write_thumb(base_item.thumb_path, img_array):
                stmt_list.append(BaseItem.insert_file_stmt(base_item))
                if len(stmt_list) == stmt_limit:
                    execute_stmt_list(stmt_list)
                    stmt_list.clear()

        stmt_list: list = []
        stmt_limit = 10

        base_item = BaseItem(entry.path)
        base_item.set_properties()
        if base_item.type_ != Static.folder_type:
            base_item.set_partial_hash()
        if entry.name.endswith(Static.img_exts):
            if os.path.exists(base_item.thumb_path):
                img_array = Utils.read_thumb(base_item.thumb_path)
            else:
                img_array = ReadImage.read_image(entry.path)
                img_array = SharedUtils.fit_image(img_array, Static.max_thumb_size)
                insert(base_item, img_array)
            qimage = Utils.qimage_from_array(img_array)
            base_item.qimage = qimage
        self.sigs.new_widget.emit(base_item)
        QTest.qSleep(SearchTask.new_wid_sleep_ms)


class FinderItemsLoader(URunnable):

    class Sigs(QObject):
        finished_ = pyqtSignal(list)

    hidden_syms: tuple[str] = ()
    sql_errors = (IntegrityError, OperationalError)

    def __init__(self, main_win_item: MainWinItem, sort_item: SortItem):
        super().__init__()
        self.sigs = FinderItemsLoader.Sigs()
        self.sort_item = sort_item
        self.main_win_item = main_win_item

        self.finder_items: dict[str, BaseItem] = {}
        self.db_items: dict[str, int] = {}
        self.conn = Dbase.get_conn(Dbase.engine)

        if not JsonData.show_hidden:
            self.hidden_syms = Static.hidden_symbols

    def task(self):
        try:
            self._task()
        except Exception as e:
            print("tasks, FinderItems error", e)
            import traceback
            print(traceback.format_exc())

    def _task(self):
        finder_items = BaseItem.sort_items(
            self.get_finder_base_items(),
            self.sort_item
        )
        self.sigs.finished_.emit(finder_items)

    def get_finder_base_items(self):
        files: list[BaseItem] = []
        for entry in os.scandir(self.main_win_item.main_dir):
            if entry.name.startswith(self.hidden_syms):
                continue
            base_item = BaseItem(entry.path)
            base_item.set_properties()
            files.append(base_item)
        return files


class FinderUrlsLoader(URunnable):

    class Sigs(QObject):
        finished_ = pyqtSignal(list)

    hidden_syms: tuple[str] = ()
    sql_errors = (IntegrityError, OperationalError)

    def __init__(self, main_win_item: MainWinItem):
        super().__init__()
        self.sigs = FinderItemsLoader.Sigs()
        self.main_win_item = main_win_item

    def task(self):
        try:
            self.sigs.finished_.emit(self._task())
        except Exception as e:
            print("tasks, FinderUrls error", e)
            # import traceback
            # print(traceback.format_exc())

    def _task(self):
        hidden_syms = () if JsonData.show_hidden else Static.hidden_symbols
        return [
            i.path
            for i in os.scandir(self.main_win_item.main_dir)
            if not i.name.startswith(hidden_syms)
        ]
        

class DbItemsLoader(URunnable):

    class Sigs(QObject):
        update_thumb = pyqtSignal(BaseItem) # на самом деле Thumb
        set_loading = pyqtSignal(BaseItem)
        finished_ = pyqtSignal()

    def __init__(self, main_win_item: MainWinItem, base_items: list[BaseItem]):
        """
        URunnable   
        Сортирует список Thumb по размеру по возрастанию для ускорения загрузки
        Загружает изображения из базы данных или создает новые
        """
        super().__init__()
        self.sigs = DbItemsLoader.Sigs()
        self.main_win_item = main_win_item
        self.base_items = base_items
        self.base_items.sort(key=lambda x: x.size)
        self.conn = Dbase.get_conn(Dbase.engine)
        self.corrupted_items: list[BaseItem] = []

    def task(self):
        """
        Создает подключение к базе данных   
        Запускает обход списка Thumb для загрузки изображений   
        Испускает сигнал finished_
        """
        self.process_thumbs()
        Dbase.close_conn(self.conn)
        self.sigs.finished_.emit()

    def process_thumbs(self):
        """
        Обходит циклом список Thumb     
        Пытается загрузить изображение из базы данных или создает новое,
        чтобы передать его в Thumb
        """
        stmt_list: list = []
        new_images: list[BaseItem] = []
        exist_images: list[BaseItem] = []
        svg_files: list[BaseItem] = []
        exist_ratings: list[BaseItem] = []
        app_files: list[BaseItem] = []

        for base_item in self.base_items:
            if not self.is_should_run():
                return
            if base_item.filename.endswith((".svg", ".SVG")):
                svg_files.append(base_item)
            if base_item.filename.endswith(Static.app_exts):
                app_files.append(base_item)
            elif base_item.type_ == Static.folder_type:
                rating = self.get_item_rating(base_item)
                if rating is None:
                    stmt_list.append(BaseItem.insert_folder_stmt(base_item))
                else:
                    base_item.rating = rating
                    stmt_list.append(BaseItem.update_folder_stmt(base_item))
                    exist_ratings.append(base_item)
            else:
                base_item.set_partial_hash()
                rating = self.get_item_rating(base_item)
                if rating is None:
                    stmt_list.append(BaseItem.insert_file_stmt(base_item))
                    if base_item.type_ in Static.img_exts:
                        new_images.append(base_item)
                else:
                    base_item.rating = rating
                    stmt_list.append(BaseItem.update_file_stmt(base_item))
                    if base_item.type_ in Static.img_exts:
                        if base_item.thumb_path and os.path.exists(base_item.thumb_path):
                            exist_images.append(base_item)
                        else:
                            new_images.append(base_item)
                    else:
                        exist_ratings.append(base_item)

        self.execute_ratings(exist_ratings)
        self.execute_app_files(app_files)
        self.execute_svg_files(svg_files)
        self.execute_exist_images(exist_images)
        self.execute_new_images(new_images)
        self.execute_stmt_list(stmt_list)
        self.execute_corrupted_images()
    
    def execute_stmt_list(self, stmt_list: list):
        for i in stmt_list:
            Dbase.execute(self.conn, i)
        Dbase.commit(self.conn)

    def execute_app_files(self, app_files: list[BaseItem], size: int = 512):
        app_folder = os.path.join(Static.thumbnails_dir, "app_icons")
        os.makedirs(app_folder, exist_ok=True)
        for i in app_files:
            if not self.is_should_run():
                break
            icns_path = Utils.get_app_icns(i.src)
            if not os.path.exists(icns_path):
                continue
            partial_hash = Utils.get_partial_hash(icns_path)
            new_icns_path = os.path.join(app_folder, partial_hash + ".icns")
            if os.path.exists(new_icns_path):
                img = Image.open(new_icns_path).convert("RGBA")
            else:
                img = Image.open(icns_path).convert("RGBA").resize((size, size))
                img.save(new_icns_path, format="PNG")
            img_array = np.array(img)
            i.qimage = Utils.qimage_from_array(img_array)
            self.update_thumb(i)

    def execute_svg_files(self, svg_files: list[BaseItem]):
        for i in svg_files:
            if not self.is_should_run():
                break
            qimage  = QImage()
            qimage.load(i.src)
            i.qimage = qimage
            self.update_thumb(i)

    def execute_ratings(self, exist_ratings: list[BaseItem]):
        for i in exist_ratings:
            if not self.is_should_run():
                break
            self.update_thumb(i)

    def execute_exist_images(self, exist_images: list[BaseItem]):
        for i in exist_images:
            if not self.is_should_run():
                break
            qimage = Utils.qimage_from_array(Utils.read_thumb(i.thumb_path))
            i.qimage = qimage
            self.update_thumb(i)

    def execute_new_images(self, new_images: list[BaseItem]):
        for i in new_images:
            if not self.is_should_run():
                break
            self.set_loading_thumb(i)
            img = ReadImage.read_image(i.src)
            if img is None:
                self.corrupted_items.append(i)
            else:
                img = SharedUtils.fit_image(img, Static.max_thumb_size)
                qimage = Utils.qimage_from_array(img)
                i.qimage = qimage
                Utils.write_thumb(i.thumb_path, img)
            self.update_thumb(i)
    
    def execute_corrupted_images(self, range_: int = 3, ms: int = 3000):
        for _ in range(range_):
            new_corrupted = []
            for i in self.corrupted_items:
                if not self.is_should_run():
                    return
                img = ReadImage.read_image(i.src)
                if img is None:
                    new_corrupted.append(i)
                    continue
                img = SharedUtils.fit_image(img, Static.max_thumb_size)
                i.qimage = Utils.qimage_from_array(img)
                Utils.write_thumb(i.thumb_path, img)
                self.update_thumb(i)
            if not new_corrupted:
                break
            self.corrupted_items = new_corrupted
            QThread.msleep(ms)

    def update_thumb(self, thumb: BaseItem):
        try:
            self.sigs.update_thumb.emit(thumb)
        except RuntimeError as e:
            self.set_should_run(False)
            print("tasks, LoadImagesTask update_thumb.emit error", e)
    
    def set_loading_thumb(self, thumb: BaseItem):
        try:
            self.sigs.set_loading.emit(thumb)
        except RuntimeError as e:
            self.set_should_run(False)
            print("tasks, LoadImagesTask set_loading.emit error", e)

    def get_item_rating(self, base_item: BaseItem) -> bool:
        stmt = sqlalchemy.select(Clmns.rating)
        if base_item.type_ == Static.folder_type:
            stmt = stmt.where(*BaseItem.get_folder_conds(base_item))
        else:
            stmt = stmt.where(Clmns.partial_hash==base_item.partial_hash)
        res = Dbase.execute(self.conn, stmt).scalar()
        return res
    

class ReadImg(URunnable):

    class Sigs(QObject):
        finished_ = pyqtSignal(tuple)

    cache_limit = 15
    cached_images: dict[str, QImage] = {}

    def __init__(self, src: str):
        super().__init__()
        self.sigs = ReadImg.Sigs()
        self.src: str = src

    def task(self):
        if self.src not in self.cached_images:
            img_array = ReadImage.read_image(self.src)
            img_array = Utils.desaturate_image(img_array, 0.2)
            if img_array is None:
                qimage = None
            else:
                qimage = Utils.qimage_from_array(img_array)
                self.cached_images[self.src] = qimage
        else:
            qimage = self.cached_images.get(self.src)
        if len(self.cached_images) > self.cache_limit:
            self.cached_images.pop(list(self.cached_images)[0])
        image_data = (self.src, qimage)
        self.sigs.finished_.emit(image_data)


class FileRemover(URunnable):

    class Sigs(QObject):
        finished_ = pyqtSignal()

    def __init__(self, main_dir: str, urls: list[str]):
        super().__init__()
        self.sigs = FileRemover.Sigs()
        self.main_dir = main_dir
        self.urls = urls

    # def task(self):
    #     try:
    #         for i in self.urls:
    #             try:
    #                 if os.path.isdir(i):
    #                     shutil.rmtree(i)
    #                 else:
    #                     os.remove(i)
    #             except Exception as e:
    #                 Utils.print_error()
    #     except Exception as e:
    #         Utils.print_error()
    #     self.sigs.finished_.emit()

    def task(self):
        subprocess.run(
            [
                "osascript",
                os.path.join(Static.scripts_dir, "remove_files.scpt")
            ] + self.urls)
        self.sigs.finished_.emit()

class PathFinderTask(URunnable):

    class Sigs(QObject):
        finished_ = pyqtSignal(str)


    def __init__(self, path: str):
        super().__init__()
        self.path = path
        self.path_finder = PathFinder(path)
        self.sigs = PathFinderTask.Sigs()

    def task(self):
        result = self.path_finder.get_result()
        if result is None:
            result = ""
        
        self.sigs.finished_.emit(result)


class ToJpegConverter(URunnable):

    class Sigs(QObject):
        finished_ = pyqtSignal(list)
        progress_value = pyqtSignal(int)
        set_progress_len = pyqtSignal(int)
        set_filename = pyqtSignal(str)

    def __init__(self, urls: list[str]):
        super().__init__()
        self.urls = urls
        self.new_urls: list[str] = []
        self.sigs = ToJpegConverter.Sigs()

    def task(self):
        urls = [i for i in self.urls if i.endswith(Static.img_exts)]
        urls.sort(key=lambda p: os.path.getsize(p))
        self.sigs.set_progress_len.emit(len(urls))
        for x, url in enumerate(urls, start=1):
            save_path = self._save_jpg(url)
            if save_path:
                self.new_urls.append(save_path)
            self.sigs.progress_value.emit(x)
            self.sigs.set_filename.emit(os.path.basename(url))
        self.sigs.finished_.emit(self.new_urls)

    def _save_jpg(self, src: str) -> None:
        try:
            img_array = ReadImage.read_image(src)
            img = Image.fromarray(img_array.astype(np.uint8))
            save_path = os.path.splitext(src)[0] + ".jpg"
            img.save(save_path, format="JPEG", quality=99)
            return save_path
        except Exception:
            Utils.print_error()
            return None


class ArchiveMaker(URunnable):

    class Sigs(QObject):
        set_max = pyqtSignal(int)
        set_value = pyqtSignal(int)
        finished_ = pyqtSignal()

    def __init__(self, files: list[str], zip_path: str):
        super().__init__()
        self.sigs = ArchiveMaker.Sigs()
        self.files = files
        self.zip_path = zip_path
        self.progress = 0
        self.all_files = self._collect_all_files()
        self.chunk_size = 8 * 1024 * 1024
        self.threshold = 100 * 1024 * 1024
        self._last_emit = 0.0  # чтобы не спамить сигналами

    def _collect_all_files(self):
        collected = []
        for item in self.files:
            if os.path.isfile(item):
                collected.append((item, os.path.basename(item)))
            elif os.path.isdir(item):
                base_dir = os.path.dirname(item)
                for root, _, files in os.walk(item):
                    for f in files:
                        full_path = os.path.join(root, f)
                        rel_path = os.path.relpath(full_path, start=base_dir)
                        collected.append((full_path, rel_path))
        return collected

    def _calc_total_chunks(self):
        total = 0
        for full_path, _ in self.all_files:
            size = os.path.getsize(full_path)
            total += (size + self.chunk_size - 1) // self.chunk_size
        return total

    def _emit_progress(self):
        now = time.monotonic()
        # обновляем максимум 5 раз в секунду
        if now - self._last_emit > 0.2:
            self._last_emit = now
            self.sigs.set_value.emit(self.progress)

    def _add_file_chunked(self, zf, full_path, arc_path):
        file_size = os.path.getsize(full_path)
        zi = zipfile.ZipInfo(arc_path)
        zi.compress_type = (
            zipfile.ZIP_STORED if file_size > self.threshold else zipfile.ZIP_DEFLATED
        )

        with zf.open(zi, "w") as dest, open(full_path, "rb", buffering=0) as src:
            while True:
                buf = src.read(self.chunk_size)
                if not buf:
                    break
                dest.write(buf)
                self.progress += 1
                self._emit_progress()

    def zip_items(self):
        total_chunks = self._calc_total_chunks()
        self.sigs.set_max.emit(total_chunks)
        self.progress = 0
        with zipfile.ZipFile(self.zip_path, "w", allowZip64=True) as zf:
            for full_path, arc_path in self.all_files:
                if not self.is_should_run():
                    break
                self._add_file_chunked(zf, full_path, arc_path)

    def task(self):
        try:
            self.zip_items()
        except Exception as e:
            print("archive maker task error:", e)
        finally:
            self.sigs.finished_.emit()


class ArchiveMaker(URunnable):

    class Sigs(QObject):
        set_max = pyqtSignal(int)
        set_value = pyqtSignal(int)
        finished_ = pyqtSignal()

    def __init__(self, files: list[str], zip_path: str):
        super().__init__()
        self.sigs = ArchiveMaker.Sigs()
        self.files = files
        self.zip_path = zip_path
        print(self.files)
        print(self.zip_path)

    def task(self):
        try:
            self._task()
        except Exception as e:
            print("ArchiveMaker error:", e)
        finally:
            self.sigs.finished_.emit()

    def _task(self):
        # собираем все файлы
        all_files = []

        for i in self.files:
            if os.path.isfile(i):
                all_files.append(i)
            elif i.endswith((".app", ".APP")):
                all_files.append(i)
            elif os.path.isdir(i):
                all_files.extend(self.scan_dir(i))

        if not all_files:
            return

        # базовый каталог
        base_dir = os.path.commonpath(all_files)
        if os.path.isfile(base_dir):
            base_dir = os.path.dirname(base_dir)

        # относительные пути
        names = [os.path.relpath(f, base_dir) for f in all_files]
        if len(all_files) > 1:
            self.sigs.set_max.emit(len(all_files))
        else:
            self.sigs.set_max.emit(0)
        # zip с чтением stdout
        p = subprocess.Popen(
            ["zip", "-r", self.zip_path, *names],
            cwd=base_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        count = 0
        for line in p.stdout:
            line = line.strip()
            if "adding" in line and len(all_files) > 1:
                count += 1
                self.sigs.set_value.emit(count)

        p.wait()

    def scan_dir(self, dir: str):
        stack: list[str] = [dir]
        files: list[str] = []
        while stack:
            current_dir = stack.pop()
            for i in os.scandir(current_dir):
                if i.is_file():
                    files.append(i.path)
                elif i.is_dir():
                    stack.append(i.path)
        return files


class ArchiveMaker(URunnable):
    class Sigs(QObject):
        set_max = pyqtSignal(int)
        set_value = pyqtSignal(int)
        finished_ = pyqtSignal()

    def __init__(self, files: list[str], zip_path: str):
        super().__init__()
        self.sigs = ArchiveMaker.Sigs()
        self.files = files
        self.zip_path = zip_path

    def task(self):
        try:
            self._task()
        except Exception as e:
            print("ArchiveMaker error:", e)
        finally:
            self.sigs.finished_.emit()

    def _task(self):
        # разделяем .app и обычные файлы/папки
        apps = [f for f in self.files if f.lower().endswith(".app")]
        others = [f for f in self.files if not f.lower().endswith(".app")]

        # временный каталог для объединения всех файлов
        import shutil
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_files = []
            self.sigs.set_max.emit(0)

            # упаковываем каждое .app через ditto в tmp каталог
            for app in apps:
                app_name = os.path.basename(app)
                tmp_app_zip = os.path.join(tmp, app_name)
                subprocess.run(["ditto", "-c", "-k", "--keepParent", app, tmp_app_zip], check=True)
                tmp_files.append(tmp_app_zip)

            # копируем обычные файлы/папки в tmp
            for f in others:
                dest = os.path.join(tmp, os.path.basename(f))
                if os.path.isfile(f):
                    shutil.copy(f, dest)
                elif os.path.isdir(f):
                    shutil.copytree(f, dest)
                tmp_files.append(dest)

            # создаём финальный архив через zip
            base_dir = tmp
            rel_paths = [os.path.relpath(f, base_dir) for f in tmp_files]

            if rel_paths:
                if len(rel_paths) > 1:
                    self.sigs.set_max.emit(len(rel_paths))
                else:
                    self.sigs.set_max.emit(0)
                count = 0

                p = subprocess.Popen(
                    ["zip", "-r", self.zip_path, *rel_paths],
                    cwd=base_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )

                for line in p.stdout:
                    line = line.strip()
                    if "adding" in line and len(rel_paths) > 1:
                        count += 1
                        self.sigs.set_value.emit(count)

                p.wait()


class ArchiveMaker(URunnable):
    class Sigs(QObject):
        set_max = pyqtSignal(int)
        set_value = pyqtSignal(int)
        finished_ = pyqtSignal()

    def __init__(self, files: list[str], zip_path: str):
        super().__init__()
        self.sigs = ArchiveMaker.Sigs()
        self.files = files
        self.zip_path = zip_path

    def task(self):
        try:
            self._task()
        except Exception as e:
            print("ArchiveMaker error:", e)
        finally:
            self.sigs.finished_.emit()

    def _task(self):
        script = os.path.join(Static.scripts_dir, "zip_files.scpt")
        root, ext = os.path.splitext(self.zip_path)
        # subprocess.run(["osascript", script, root] + self.files)
        
        cmd = ["open", "-a", "/System/Library/CoreServices/Applications/Archive Utility.app"] + self.files
        subprocess.run(cmd)


class DataSizeCounter(URunnable):
    
    class Sigs(QObject):
        finished_ = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.sigs = DataSizeCounter.Sigs()

    def task(self):
        try:
            self.sigs.finished_.emit(Utils.get_hashdir_size())
        except Exception as e:
            print("tasks, DataSize error", e)


class AutoCacheCleaner(URunnable):

    class Sigs(QObject):
        finished_ = pyqtSignal()

    def __init__(self):
        """
        При достижении лимита данных, заданного пользователем, будет удалено
        10% данных (самых старых и невостребованных)
        """
        super().__init__()
        self.sigs = AutoCacheCleaner.Sigs()
        self.limit = Static.limit_mappings[JsonData.data_limit]["bytes"] * 0.9
        self.conn = Dbase.get_conn(Dbase.engine)
        self.stmt_limit = 200

    def task(self):
        try:
            self._task()
            Dbase.close_conn(self.conn)
        except Exception as e:
            print("tasks, ClearData error", e)

    def _task(self):
        data = Utils.get_hashdir_size()
        total_size = data["total"]
        while total_size > self.limit:
            limited_select = self.get_limited_select()
            if not limited_select:
                break
            thumb_path_list = []
            for thumb_path in limited_select:
                if not self.is_should_run():
                    self.remove_from_db(thumb_path_list)
                    return
                if thumb_path and os.path.exists(thumb_path):
                    thumb_size = os.path.getsize(thumb_path)
                    if self.remove_file(thumb_path):
                        total_size -= thumb_size
                        thumb_path_list.append(thumb_path)
            if not thumb_path_list:
                break
            self.remove_from_db(thumb_path_list)

    def get_limited_select(self):
        conds = sqlalchemy.and_(
            Clmns.rating == 0,
            Clmns.thumb_path.isnot(None),
            Clmns.thumb_path != ""
        )
        stmt = (
            sqlalchemy.select(Clmns.thumb_path)
            .order_by(Clmns.last_read.asc())
            .limit(self.stmt_limit)
            .where(conds)
        )
        return Dbase.execute(self.conn, stmt).scalars()
    
    def remove_file(self, thumb_path):
        try:
            root = os.path.dirname(thumb_path)
            os.remove(thumb_path)
            if os.path.exists(root) and not os.listdir(root):
                shutil.rmtree(root)
            return True
        except Exception as e:
            print("tasks, ClearData error", e)
            return None

    def remove_from_db(self, thumb_path_list: list[int]):
        conds = sqlalchemy.and_(
            Clmns.thumb_path.in_(thumb_path_list),
            Clmns.rating==0
        )
        stmt = sqlalchemy.delete(CACHE).where(conds)
        Dbase.execute(self.conn, stmt)
        Dbase.commit(self.conn)


class CustomSizeCacheCleaner(URunnable):

    class Sigs(QObject):
        finished_ = pyqtSignal(int)

    def __init__(self, bytes_limit: int = 200 * 1024 * 1024):
        "Удаляет заданный размер данных"
    
        super().__init__()
        self.sigs = CustomSizeCacheCleaner.Sigs()
        self.bytes_limit = bytes_limit
        self.conn = Dbase.get_conn(Dbase.engine)
        self.stmt_limit = 200
        self.removed_size = 0

    def task(self):
        try:
            self._task()
            Dbase.close_conn(self.conn)
        except Exception as e:
            print("tasks, ClearData error", e)
        self.sigs.finished_.emit(self.removed_size)

    def _task(self):
        while self.removed_size < self.bytes_limit:
            limited_select = self.get_limited_select()
            if not limited_select:
                break
            thumb_path_list = []
            for thumb_path in limited_select:
                if not self.is_should_run():
                    self.remove_from_db(thumb_path_list)
                    return
                if thumb_path and os.path.exists(thumb_path):
                    thumb_size = os.path.getsize(thumb_path)
                    if self.remove_file(thumb_path):
                        self.removed_size += thumb_size
                        thumb_path_list.append(thumb_path)
            if not thumb_path_list:
                break
            self.remove_from_db(thumb_path_list)

        self.remove_from_db(thumb_path_list)

    def get_limited_select(self):
        conds = sqlalchemy.and_(
            Clmns.rating == 0,
            Clmns.thumb_path.isnot(None),
            Clmns.thumb_path != ""
        )
        stmt = (
            sqlalchemy.select(Clmns.thumb_path)
            .order_by(Clmns.last_read.asc())
            .limit(self.stmt_limit)
            .where(conds)
        )
        return Dbase.execute(self.conn, stmt).scalars()
    
    def remove_file(self, thumb_path):
        try:
            root = os.path.dirname(thumb_path)
            os.remove(thumb_path)
            if os.path.exists(root) and not os.listdir(root):
                shutil.rmtree(root)
            return True
        except Exception as e:
            print("tasks, ClearData error", e)
            return None

    def remove_from_db(self, thumb_path_list: list[int]):
        conds = sqlalchemy.and_(
            Clmns.thumb_path.in_(thumb_path_list),
            Clmns.rating==0
        )
        stmt = sqlalchemy.delete(CACHE).where(conds)
        Dbase.execute(self.conn, stmt)
        Dbase.commit(self.conn)


class CacheDownloader(URunnable):

    class Sigs(QObject):
        progress = pyqtSignal(int)
        progress_txt = pyqtSignal(str)
        prorgess_max = pyqtSignal(int)
        filename = pyqtSignal(str)
        caching = pyqtSignal()
        finished_ = pyqtSignal()

    from_text = "из"

    def __init__(self, dirs: list[str]):
        super().__init__()
        self.dirs = dirs
        self.sigs = CacheDownloader.Sigs()
        self.conn = Dbase.get_conn(Dbase.engine)

    def task(self):
        try:
            self._task()
        except Exception as e:
            # print("tasks CacheDownloader error", e)
            import traceback
            print(traceback.format_exc())

        self.sigs.finished_.emit()
        Dbase.close_conn(self.conn)
        print("cache downloader finished")

    def _task(self):
        new_images = self.prepare_images()
        stmt_list = []
        stmt_limit = 10

        self.sigs.prorgess_max.emit(len(new_images))
        self.sigs.caching.emit()
        for x, data in enumerate(new_images, start=1):
            if not self.is_should_run():
                if stmt_list:
                    self.execute_stmt_list(stmt_list)
                return
            self.sigs.progress.emit(x)
            self.sigs.progress_txt.emit(f"{x} {self.from_text} {len(new_images)}")
            base_item: BaseItem = data["base_item"]
            if self.write_thumb(base_item):
                stmt_list.append(data["stmt"])
                if len(stmt_list) == stmt_limit:
                    self.execute_stmt_list(stmt_list)
                    stmt_list.clear()

        if stmt_list:
            self.execute_stmt_list(stmt_list)

    def execute_stmt_list(self, stmt_list: list):
        for i in stmt_list:
            Dbase.execute(self.conn, i)
        Dbase.commit(self.conn)

    def prepare_images(self):
        new_images: list[dict[BaseItem, str]] = []
        stack = [*self.dirs]

        while stack:
            last_dir = stack.pop()
            for i in os.scandir(last_dir):
                if not self.is_should_run():
                    return new_images
                if i.is_dir():
                    stack.append(i.path)
                elif i.name.endswith(Static.img_exts):
                    # print("prepare base item", i.path)
                    self.sigs.filename.emit(self.cut_filename(i.name))
                    base_item = BaseItem(i.path)
                    base_item.set_properties()
                    base_item.set_partial_hash()
                    if self.exists_check(base_item) is None:
                        new_images.append({
                            "base_item": base_item,
                            "stmt": BaseItem.insert_file_stmt(base_item)
                        })
        return new_images

    def exists_check(self, base_item: BaseItem):
        stmt = (
            sqlalchemy.select(Clmns.id)
            .where(Clmns.partial_hash == base_item.partial_hash)
        )
        return Dbase.execute(self.conn, stmt).scalar() or None
    
    def cut_filename(self, text: str, limit: int = 25):
        if len(text) > limit:
            return text[:limit] + "..."
        return text

    def write_thumb(self, base_item: BaseItem):
        img = ReadImage.read_image(base_item.src)
        img = SharedUtils.fit_image(img, Static.max_thumb_size)
        return Utils.write_thumb(base_item.thumb_path, img)
    


class ImgRes(URunnable):

    class Sigs(QObject):
        finished_ = pyqtSignal(str)

    undef_text = "Неизвестно"

    def __init__(self, src: str):
        super().__init__()
        self.src = src
        self.sigs = ImgRes.Sigs()

    def task(self):
        img_ = ReadImage.read_image(self.src)
        if img_ is not None and len(img_.shape) > 1:
            h, w = img_.shape[0], img_.shape[1]
            resol= f"{w}x{h}"
        else:
            resol = self.undef_text
        self.sigs.finished_.emit(resol)


class MultipleItemsInfo(URunnable):

    class Sigs(QObject):
        finished_ = pyqtSignal(dict)

    err = " Произошла ошибка"

    def __init__(self, items: list[BaseItem]):
        super().__init__()
        self.items = items
        self.sigs = MultipleItemsInfo.Sigs()

        self.total_size = 0
        self.total_files = 0
        self.total_folders = 0

    def task(self):
        try:
            self._task()
            self.sigs.finished_.emit({
                "total_size": SharedUtils.get_f_size(self.total_size),
                "total_files": format(self.total_files, ",").replace(",", " "),
                "total_folders": format(self.total_folders, ",").replace(",", " ")
            })
        except Exception as e:
            print("tasks, MultipleInfoFiles error", e)
            self.sigs.finished_.emit({
                "total_size": self.err,
                "total_files": self.err,
                "total_folders": self.err
            })

    def _task(self):
        for i in self.items:
            if i.type_ == Static.folder_type:
                self.get_folder_size(i)
                self.total_folders += 1
            else:
                self.total_size += i.size
                self.total_files += 1

    def get_folder_size(self, base_item: BaseItem):
        stack = [base_item.src]
        while stack:
            current_dir = stack.pop()
            try:
                os.listdir(current_dir)
            except Exception as e:
                print("tasks, MultipleItemsInfo error", e)
                continue
            with os.scandir(current_dir) as entries:
                for entry in entries:
                    try:
                        if entry.is_dir():
                            self.total_folders += 1
                            stack.append(entry.path)
                    except Exception as e:
                        print("tasks, MultipleItemsInfo error", e)
                    else:
                        try:
                            self.total_size += entry.stat().st_size
                            self.total_files += 1
                        except Exception as e:
                            print("tasks, MultipleItemsInfo error", e)
                            continue


class FileInfo(URunnable):

    class Sigs(QObject):
        finished_info = pyqtSignal(dict)
        finished_calc = pyqtSignal(str)

    ru_folder = "Папка: "
    calculating = "Вычисляю..."
    name_text = "Имя: "
    type_text = "Тип: "
    size_text = "Размер: "
    src_text = "Место: "
    mod_text = "Изменен: "
    resol_text = "Разрешение: "
    row_limit = 50

    def __init__(self, base_item: BaseItem):
        super().__init__()
        self.base_item = base_item
        self.signals = FileInfo.Sigs()

    def task(self) -> dict[str, str| int]:
        if self.base_item.type_ == Static.folder_type:
            size_ = self.calculating
            type_ = self.ru_folder
        else:
            size_ = SharedUtils.get_f_size(self.base_item.size)
            type_ = self.base_item.type_
        
        name = self.lined_text(self.base_item.filename)
        src = self.lined_text(self.base_item.src)
        mod = SharedUtils.get_f_date(self.base_item.mod)

        data = {
            FileInfo.name_text: name,
            FileInfo.type_text: type_,
            FileInfo.mod_text: mod,
            FileInfo.src_text: src,
            FileInfo.size_text: size_,
            }
        
        if self.base_item.type_ != Static.folder_type:
            data.update({FileInfo.resol_text: self.calculating})

        self.signals.finished_info.emit(data)

    def lined_text(self, text: str):
        if len(text) > FileInfo.row_limit:
            text = [
                text[i:i + FileInfo.row_limit]
                for i in range(0, len(text), FileInfo.row_limit)
                ]
            return "\n".join(text)
        else:
            return text


class _DirChangedHandler(FileSystemEventHandler):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def on_any_event(self, event):
        self.callback(event)


class DirWatcher(URunnable):

    class Sigs(QObject):
        changed = pyqtSignal(object)

    def __init__(self, path: str):
        super().__init__()
        self.path = path
        self.sigs = DirWatcher.Sigs()

    def on_dirs_changed(self, e: FileSystemEvent):
        if e.src_path != self.path:
            self.sigs.changed.emit(e)
            # print(e.event_type)

    def task(self):
        try:
            self._task()
        except Exception as e:
            print("tasks > DirWatcher error", e)

    def _task(self):
        observer = Observer()
        handler = _DirChangedHandler(lambda e: self.sigs.changed.emit(e.src_path))
        handler = _DirChangedHandler(lambda e: self.on_dirs_changed(e))
        observer.schedule(handler, self.path, recursive=False)
        observer.start()
        try:
            while self.is_should_run():
                QThread.msleep(1000)
        finally:
            observer.stop()
            observer.join()