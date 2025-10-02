import difflib
import gc
import os
import plistlib
import shutil
import zipfile
from time import sleep

import numpy as np
import sqlalchemy
from PIL import Image
from PyQt5.QtCore import QObject, QRunnable, QThreadPool, QTimer, pyqtSignal
from PyQt5.QtGui import QImage
from PyQt5.QtTest import QTest
from sqlalchemy.exc import IntegrityError, OperationalError

from cfg import JsonData, Static, ThumbData
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


# Общий класс для выполнения действий QAction в отдельном потоке
class ActionsTask(URunnable):
    def __init__(self,  cmd_: callable):
        super().__init__()
        self.cmd_ = cmd_

    def task(self):
        self.cmd_()


class _CopyFilesSigs(QObject):
    finished_ = pyqtSignal(list)
    set_copied_kb = pyqtSignal(int)
    set_total_kb = pyqtSignal(int)
    set_counter = pyqtSignal(tuple)
    error_win = pyqtSignal()
    replace_files_win = pyqtSignal()


class CopyFilesTask(URunnable):
    def __init__(self):
        super().__init__()
        self.sigs = _CopyFilesSigs()
        self.pause_flag = False
        self.copied_kb = 0
        self.thumb_paths: list[str] = []
        self.src_dest_list: list[tuple[str, str]] = []

        self.copied_timer = QTimer()
        self.copied_timer.timeout.connect(self.send_copied_kb)
        self.copied_timer.start(1000)

    def prepare_same_dir(self):
        """
        Если файлы и папки скопированы в одной директории и будут вставлены туда же,
        то они будут вставлены с припиской "копия"
        """
        for src_url in CopyItem.urls:
            if os.path.isfile(src_url):
                new_filename = self.add_copy_to_name(src_url)
                self.src_dest_list.append((src_url, new_filename))
                self.thumb_paths.append(new_filename)
            else:
                new_dir_name = self.add_copy_to_name(src_url)
                # получаем все url файлов для папки
                # заменяем имя старой папки на имя новой папки
                nested_urls = [
                    (x, x.replace(src_url, new_dir_name))
                    for x in self.get_nested_urls(src_url)
                ]
                self.src_dest_list.extend(nested_urls)
                self.thumb_paths.append(new_dir_name)
    
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
                self.thumb_paths.append(new_filename)
            else:
                new_dir_name = src_url.replace(CopyItem.get_src(), CopyItem.get_dest())
                # получаем все url файлов для папки
                # заменяем имя старой папки на имя новой папки
                nested_urls = [
                    (x, x.replace(CopyItem.get_src(), CopyItem.get_dest()))
                    for x in self.get_nested_urls(src_url)
                ]
                self.src_dest_list.extend(nested_urls)
                self.thumb_paths.append(new_dir_name)

        for src, dest in self.src_dest_list:
            if os.path.exists(dest):
                self.sigs.replace_files_win.emit()
                self.pause_flag = True
                while self.pause_flag:
                    sleep(1)
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
            self.thumb_paths.append(full_path)

    def task(self):
        if CopyItem.get_is_search():
            self.prepare_search_dir()
        elif CopyItem.get_src() == CopyItem.get_dest():
            self.prepare_same_dir()
        else:
            self.prepare_another_dir()

        # for i in self.src_dest_list:
        #     print(i)

        total_bytes = 0
        for src, dest in self.src_dest_list:
            total_bytes += os.path.getsize(src)
        self.sigs.set_total_kb.emit(self.bytes_to_kb(total_bytes))

        for count, (src, dest) in enumerate(self.src_dest_list, start=1):
            if not self.is_should_run():
                break
            data = (count, len(self.src_dest_list))
            self.sigs.set_counter.emit(data)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            try:
                self.copy_by_bytes(src, dest)
            except Exception as e:
                Utils.print_error()
                self.sigs.error_win.emit()
                break
            if CopyItem.get_is_cut() and not CopyItem.get_is_search():
                if os.path.isdir(src):
                    shutil.rmtree(src)
                else:
                    os.remove(src)
        self.sigs.finished_.emit(self.thumb_paths)

    def bytes_to_kb(self, bytes: int):
        return int(bytes / (1024 * 1024))

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

    def copy_by_bytes(self, src: str, dest: str):
        tmp = True
        buffer_size = 1024 * 1024  # 1 MB
        with open(src, 'rb') as fsrc, open(dest, 'wb') as fdest:
            while tmp:
                buf = fsrc.read(buffer_size)
                if not buf:
                    break
                if not self.is_should_run():
                    return
                fdest.write(buf)
                # прибавляем в байтах сколько уже скопировано
                buf = self.bytes_to_kb(len(buf))
                self.copied_kb += buf
    
    def send_copied_kb(self):
        self.sigs.set_copied_kb.emit(self.copied_kb)


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
        if self.base_item.type_ == Static.FOLDER_TYPE:
            stmt = stmt.where(*BaseItem.get_folder_conds(self.base_item))
        else:
            stmt = stmt.where(Clmns.partial_hash==self.base_item.partial_hash)
        stmt = stmt.values(rating=self.new_rating)
        Dbase.execute(conn, stmt)
        Dbase.commit(conn)
        Dbase.close_conn(conn)
        self.sigs.finished_.emit()


class _SearchSigs(QObject):
    new_widget = pyqtSignal(BaseItem)
    finished_ = pyqtSignal(list)


class SearchTask(URunnable):
    sleep_ms = 1000
    new_wid_sleep_ms = 200
    ratio = 0.85

    def __init__(self, main_win_item: MainWinItem, search_item: SearchItem):
        super().__init__()
        self.sigs = _SearchSigs()
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
        Dbase.commit(self.conn)
        self.conn.close()

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
            if entry.name.startswith(Static.hidden_file_syms):
                continue
            if entry.is_dir():
                dirs_list.append(entry.path)
                # continue
            if self.process_entry(entry):
                self.process_img(entry)

    def process_img(self, entry: os.DirEntry):

        def insert(base_item: BaseItem, img_array: np.ndarray):
            stmt = BaseItem.insert_file_stmt(base_item)
            Dbase.execute(self.conn, stmt)
            Utils.write_thumb(base_item.thumb_path, img_array)
            self.insert_count += 1
            if self.insert_count > 10:
                self.insert_count = 0
                Dbase.commit(self.conn)

        base_item = BaseItem(entry.path)
        base_item.set_properties()
        base_item.partial_hash = Utils.get_partial_hash(entry.path)
        base_item.thumb_path = Utils.get_abs_thumb_path(base_item.partial_hash)
        if entry.name.endswith(Static.ext_all):
            if os.path.exists(base_item.thumb_path):
                img_array = Utils.read_thumb(base_item.thumb_path)
            else:
                img_array = ReadImage.read_image(entry.path)
                img_array = SharedUtils.fit_image(img_array, ThumbData.DB_IMAGE_SIZE)
                insert(base_item, img_array)
            qimage = Utils.qimage_from_array(img_array)
            base_item.qimage = qimage
        self.sigs.new_widget.emit(base_item)
        QTest.qSleep(SearchTask.new_wid_sleep_ms)


class FinderItems(URunnable):

    class Sigs(QObject):
        finished_ = pyqtSignal(list)

    hidden_syms: tuple[str] = ()
    sql_errors = (IntegrityError, OperationalError)

    def __init__(self, main_win_item: MainWinItem, sort_item: SortItem):
        super().__init__()
        self.sigs = FinderItems.Sigs()
        self.sort_item = sort_item
        self.main_win_item = main_win_item

        self.finder_items: dict[str, BaseItem] = {}
        self.db_items: dict[str, int] = {}
        self.conn = Dbase.get_conn(Dbase.engine)

        if not JsonData.show_hidden:
            self.hidden_syms = Static.hidden_file_syms

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


class LoadImagesTask(URunnable):

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
        self.sigs = LoadImagesTask.Sigs()
        self.main_win_item = main_win_item
        self.base_items = base_items
        key_ = lambda x: x.size
        self.base_items.sort(key=key_)
        self.conn = Dbase.get_conn(Dbase.engine)

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
            if base_item.filename.endswith((".app", ".APP")):
                app_files.append(base_item)
            elif base_item.type_ == Static.FOLDER_TYPE:
                rating = self.get_item_rating(base_item)
                if rating is None:
                    stmt_list.append(BaseItem.insert_folder_stmt(base_item))
                else:
                    base_item.rating = rating
                    stmt_list.append(BaseItem.update_folder_stmt(base_item))
                    exist_ratings.append(base_item)
            else:
                base_item.partial_hash = Utils.get_partial_hash(base_item.src)
                base_item.thumb_path = Utils.get_abs_thumb_path(base_item.partial_hash)
                rating = self.get_item_rating(base_item)
                if rating is None:
                    stmt_list.append(BaseItem.insert_file_stmt(base_item))
                    if base_item.type_ in Static.ext_all:
                        new_images.append(base_item)
                else:
                    base_item.rating = rating
                    stmt_list.append(BaseItem.update_file_stmt(base_item))
                    if base_item.type_ in Static.ext_all:
                        exist_images.append(base_item)
                    else:
                        exist_ratings.append(base_item)

        self.execute_ratings(exist_ratings)
        self.execute_app_files(app_files)
        self.execute_svg_files(svg_files)
        self.execute_exist_images(exist_images)
        self.execute_new_images(new_images)
        self.execute_stmt_list(stmt_list)
    
    def execute_stmt_list(self, stmt_list: list):
        for i in stmt_list:
            Dbase.execute(self.conn, i)
        Dbase.commit(self.conn)

    def execute_app_files(self, app_files: list[BaseItem]):
        for i in app_files:
            if not self.is_should_run():
                break
            plist_path = os.path.join(i.src, "Contents", "info.plist")
            with open(plist_path, "rb") as f:
                plist = plistlib.load(f)
            icon_name = plist.get("CFBundleIconFile")
            if not icon_name.endswith(".icns"):
                icon_name += ".icns"
            icns_path = os.path.join(i.src, "Contents", "Resources", icon_name)
            qimage = QImage()
            qimage.load(icns_path)
            i.qimage = qimage
            try:
                self.sigs.update_thumb.emit(i)
            except RuntimeError as e:
                print("tasks, LoadImagesTask, update_thumb.emit error", e)
                self.set_should_run(False)

    def execute_svg_files(self, svg_files: list[BaseItem]):
        for i in svg_files:
            if not self.is_should_run():
                break
            qimage  = QImage()
            qimage.load(i.src)
            i.qimage = qimage
            try:
                self.sigs.update_thumb.emit(i)
            except RuntimeError as e:
                print("tasks, LoadImagesTask, update_thumb.emit error", e)
                self.set_should_run(False)

    def execute_ratings(self, exist_ratings: list[BaseItem]):
        for i in exist_ratings:
            if not self.is_should_run():
                break
            try:
                self.sigs.update_thumb.emit(i)
            except RuntimeError as e:
                print("tasks, LoadImagesTask update_thumb.emit error", e)
                self.set_should_run(False)

    def execute_exist_images(self, exist_images: list[BaseItem]):
        for i in exist_images:
            if not self.is_should_run():
                break
            qimage = Utils.qimage_from_array(Utils.read_thumb(i.thumb_path))
            i.qimage = qimage
            try:
                self.sigs.update_thumb.emit(i)
            except RuntimeError as e:
                print("tasks, LoadImagesTask update_thumb.emit error", e)
                self.set_should_run(False)

    def execute_new_images(self, new_images: list[BaseItem]):
        for i in new_images:
            if not self.is_should_run():
                break
            try:
                self.sigs.set_loading.emit(i)
            except RuntimeError as e:
                print("tasks, LoadImagesTask update_thumb.emit error", e)
                self.set_should_run(False)
                break
            img = ReadImage.read_image(i.src)
            img = SharedUtils.fit_image(img, ThumbData.DB_IMAGE_SIZE)
            qimage = Utils.qimage_from_array(img)
            i.qimage = qimage
            Utils.write_thumb(i.thumb_path, img)
            try:
                self.sigs.update_thumb.emit(i)
            except RuntimeError as e:
                self.set_should_run(False)
                print("tasks, LoadImagesTask update_thumb.emit error", e)
                break

    def get_item_rating(self, base_item: BaseItem) -> bool:
        stmt = sqlalchemy.select(Clmns.rating)
        if base_item.type_ == Static.FOLDER_TYPE:
            stmt = stmt.where(*BaseItem.get_folder_conds(base_item))
        else:
            stmt = stmt.where(Clmns.partial_hash==base_item.partial_hash)
        res = Dbase.execute(self.conn, stmt).scalar()
        return res
    

class _LoadImgSigs(QObject):
    finished_ = pyqtSignal(tuple)


class LoadImgTask(URunnable):
    cache_limit = 15
    cached_images: dict[str, QImage] = {}

    def __init__(self, src: str):
        super().__init__()
        self.sigs = _LoadImgSigs()
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
            # del img_array
            # gc.collect()
        else:
            qimage = self.cached_images.get(self.src)
        if len(self.cached_images) > self.cache_limit:
            self.cached_images.pop(list(self.cached_images)[0])
        image_data = (self.src, qimage)
        self.sigs.finished_.emit(image_data)


class _InfoTaskSigs(QObject):
    finished_info = pyqtSignal(dict)
    finished_calc = pyqtSignal(str)


class ImgResolTask(URunnable):
    undef_text = "Неизвестно"

    def __init__(self, base_item: BaseItem):
        super().__init__()
        self.base_item = base_item
        self.sigs = _InfoTaskSigs()

    def task(self):
        img_ = ReadImage.read_image(self.base_item.src)
        if img_ is not None and len(img_.shape) > 1:
            h, w = img_.shape[0], img_.shape[1]
            resol= f"{w}x{h}"
        else:
            resol = self.undef_text
        
        self.sigs.finished_calc.emit(resol)


class FolderSizeTask(URunnable):
    undef_text = "Неизвестно"

    def __init__(self, base_item: BaseItem):
        super().__init__()
        self.base_item = base_item
        self.sigs = _InfoTaskSigs()

    def task(self):
        try:
            total = self.get_folder_size()
        except Exception:
            Utils.print_error()
            total = self.undef_text

        self.sigs.finished_calc.emit(total)

    def get_folder_size(self):
        total = 0
        stack = []
        stack.append(self.base_item.src)
        while stack:
            current_dir = stack.pop()
            with os.scandir(current_dir) as entries:
                for entry in entries:
                    if entry.is_dir():
                        stack.append(entry.path)
                    else:
                        total += entry.stat().st_size
        return SharedUtils.get_f_size(total)


class InfoTask(URunnable):
    ru_folder = "Папка"
    calculating = "Вычисляю..."
    name_text = "Имя"
    type_text = "Тип"
    size_text = "Размер"
    src_text = "Место"
    mod_text = "Изменен"
    resol_text = "Разрешение"
    row_limit = 50

    def __init__(self, base_item: BaseItem):
        super().__init__()
        self.base_item = base_item
        self.signals = _InfoTaskSigs()

    def task(self) -> dict[str, str| int]:
        if self.base_item.type_ == Static.FOLDER_TYPE:
            size_ = self.calculating
            type_ = self.ru_folder
        else:
            size_ = SharedUtils.get_f_size(self.base_item.size)
            type_ = self.base_item.type_
        
        name = self.lined_text(self.base_item.filename)
        src = self.lined_text(self.base_item.src)
        mod = SharedUtils.get_f_date(self.base_item.mod)

        data = {
            InfoTask.name_text: name,
            InfoTask.type_text: type_,
            InfoTask.mod_text: mod,
            InfoTask.src_text: src,
            InfoTask.size_text: size_,
            }
        
        if self.base_item.type_ != Static.FOLDER_TYPE:
            data.update({InfoTask.resol_text: self.calculating})

        self.signals.finished_info.emit(data)

    def lined_text(self, text: str):
        if len(text) > InfoTask.row_limit:
            text = [
                text[i:i + InfoTask.row_limit]
                for i in range(0, len(text), InfoTask.row_limit)
                ]
            return "\n".join(text)
        else:
            return text
        

class _RemoveFilesSigs(QObject):
    finished_ = pyqtSignal()


class RemoveFilesTask(URunnable):
    def __init__(self, main_dir: str, urls: list[str]):
        super().__init__()
        self.sigs = _RemoveFilesSigs()
        self.main_dir = main_dir
        self.urls = urls

    def task(self):
        try:
            for i in self.urls:
                try:
                    if os.path.isdir(i):
                        shutil.rmtree(i)
                    else:
                        os.remove(i)
                except Exception as e:
                    Utils.print_error()
        except Exception as e:
            Utils.print_error()
        self.sigs.finished_.emit()


class _PathFinderSigs(QObject):
    finished_ = pyqtSignal(str)


class PathFinderTask(URunnable):
    def __init__(self, path: str):
        super().__init__()
        self.path = path
        self.path_finder = PathFinder(path)
        self.sigs = _PathFinderSigs()

    def task(self):
        result = self.path_finder.get_result()
        if result is None:
            result = ""
        
        self.sigs.finished_.emit(result)


class _ImgConvertSigs(QObject):
    finished_ = pyqtSignal(list)
    progress_value = pyqtSignal(int)
    set_progress_len = pyqtSignal(int)


class ImgConvertTask(URunnable):
    def __init__(self, urls: list[str]):
        super().__init__()
        self.urls = urls
        self.new_urls: list[str] = []
        self.sigs = _ImgConvertSigs()

    def task(self):
        urls = [i for i in self.urls if i.endswith(Static.ext_all)]
        self.sigs.set_progress_len.emit(len(urls))
        for x, url in enumerate(urls, start=1):
            save_path = self._save_jpg(url)
            if save_path:
                self.new_urls.append(save_path)
            self.sigs.progress_value.emit(x)
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
        

class _ArchiveSigs(QObject):
    set_max = pyqtSignal(int)
    set_value = pyqtSignal(int)
    finished_ = pyqtSignal()


class ArchiveTask(URunnable):
    def __init__(self, files: list[str], zip_path: str):
        super().__init__()
        self.sigs = _ArchiveSigs()
        self.files = files
        self.zip_path = zip_path
        self.progress = 0
        self.all_files = self._collect_all_files()

        self.chunk_size: int = 8*1024*1024
        self.threshold: int = 100*1024*1024

    def _collect_all_files(self) -> list[tuple[str, str]]:
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

    def _calc_total_chunks(self) -> int:
        total = 0
        for full_path, _ in self.all_files:
            size = os.path.getsize(full_path)
            total += (size + self.chunk_size - 1) // self.chunk_size
        return total

    def _add_file_chunked(self, zf: zipfile.ZipFile, full_path: str, arc_path: str):
        file_size = os.path.getsize(full_path)
        zi = zipfile.ZipInfo(arc_path)
        zi.compress_type = zipfile.ZIP_STORED if file_size > self.threshold else zipfile.ZIP_DEFLATED
        with zf.open(zi, mode="w") as dest, open(full_path, "rb") as src:
            while True:
                buf = src.read(self.chunk_size)
                if not buf:
                    break
                dest.write(buf)
                self.progress += 1
                self.sigs.set_value.emit(self.progress)

    def zip_items(self):
        total_chunks = self._calc_total_chunks()
        self.sigs.set_max.emit(total_chunks)
        self.progress = 0

        with zipfile.ZipFile(self.zip_path, 'w') as zf:
            for full_path, arc_path in self.all_files:
                if not self.is_should_run():
                    break
                self._add_file_chunked(zf, full_path, arc_path)

    def task(self):
        self.zip_items()
        self.sigs.finished_.emit()


class DataSize(URunnable):
    
    class Sigs(QObject):
        finished_ = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.sigs = DataSize.Sigs()

    def task(self):
        try:
            self.sigs.finished_.emit(Utils.get_hashdir_size())
        except Exception as e:
            print("tasks, DataSize error", e)


class CacheCleaner(URunnable):

    class Sigs(QObject):
        finished_ = pyqtSignal()

    def __init__(self):
        """
        При достижении лимита данных, заданного пользователем, будет удалено
        10% данных (самых старых и невостребованных)
        """
        super().__init__()
        self.sigs = CacheCleaner.Sigs()
        self.limit = Static.DATA_LIMITS[JsonData.data_limit]["bytes"] * 0.9
        self.conn = Dbase.get_conn(Dbase.engine)
        self.stmt_limit = 200

    def task(self):
        try:
            self._task()
            Dbase.close_conn(self.conn)
        except Exception as e:
            print("tasks, ClearData error", e)

    def get_limited_select(self):
        stmt = (
            sqlalchemy.select(Clmns.id, Clmns.thumb_path)
            .order_by(Clmns.last_read.asc())
            .limit(self.stmt_limit)
        )
        return Dbase.execute(self.conn, stmt).fetchall()
    
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

    def remove_id_list(self, id_list: list[int]):
        stmt = (
            sqlalchemy.delete(CACHE)
            .where(Clmns.id.in_(id_list))
        )
        Dbase.execute(self.conn, stmt)
        Dbase.commit(self.conn)

    def _task(self):
        data = Utils.get_hashdir_size()
        total_size = data["total"]
        while total_size > self.limit:
            limited_select = self.get_limited_select()
            if not limited_select:
                break
            id_list = []
            for id_, thumb_path in limited_select:
                if thumb_path and os.path.exists(thumb_path):
                    thumb_size = os.path.getsize(thumb_path)
                    if self.remove_file(thumb_path):
                        total_size -= thumb_size
                        id_list.append(id_)
            if not id_list:
                break
            self.remove_id_list(id_list)


class LimitedCacheCleaner(URunnable):

    class Sigs(QObject):
        finished_ = pyqtSignal()

    def __init__(self, bytes_limit: int = 200 * 1024 * 1024):
        "Удаляет 200 мегабайт данных"
    
        super().__init__()
        self.sigs = LimitedCacheCleaner.Sigs()
        self.bytes_limit = bytes_limit
        self.conn = Dbase.get_conn(Dbase.engine)
        self.stmt_limit = 200

    def task(self):
        try:
            self._task()
            Dbase.close_conn(self.conn)
        except Exception as e:
            print("tasks, ClearData error", e)

    def get_limited_select(self):
        stmt = (
            sqlalchemy.select(Clmns.id, Clmns.thumb_path)
            .order_by(Clmns.last_read.asc())
            .limit(self.stmt_limit)
        )
        return Dbase.execute(self.conn, stmt).fetchall()
    
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

    def remove_id_list(self, id_list: list[int]):
        stmt = (
            sqlalchemy.delete(CACHE)
            .where(Clmns.id.in_(id_list))
        )
        Dbase.execute(self.conn, stmt)
        Dbase.commit(self.conn)

    def _task(self):
        removed_size = 0
        while removed_size < self.bytes_limit:
            limited_select = self.get_limited_select()
            if not limited_select:
                break
            id_list = []
            for id_, thumb_path in limited_select:
                if thumb_path and os.path.exists(thumb_path):
                    thumb_size = os.path.getsize(thumb_path)
                    if self.remove_file(thumb_path):
                        removed_size += thumb_size
                        id_list.append(id_)
            if not id_list:
                break
            self.remove_id_list(id_list)