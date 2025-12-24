import difflib
import gc
import glob
import json
import os
import shutil
import subprocess
import threading
import time
import zipfile

import numpy as np
import sqlalchemy
from PIL import Image
from PyQt5.QtCore import (QObject, QRunnable, Qt, QThread, QThreadPool, QTimer,
                          pyqtSignal)
from PyQt5.QtGui import QImage
from PyQt5.QtTest import QTest
from sqlalchemy.exc import IntegrityError, OperationalError
from watchdog.events import FileSystemEventHandler
from watchdog.observers.polling import PollingObserver as Observer

from cfg import Dynamic, JsonData, Static
from system.shared_utils import PathFinder, ReadImage, SharedUtils

from .database import CACHE, Clmns, Dbase
from .items import CopyItem, DataItem, MainWinItem, SearchItem, SortItem
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
        # cls.pool.setMaxThreadCount(5)

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
        self.total_size = 0
        self.copied_count = 0
        self.total_count = 0

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
                self.toggle_pause_flag(True)
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

        for src, dest in self.src_dest_list:
            self.total_size += os.path.getsize(src)
        self.total_count = len(self.src_dest_list)

        self.sigs.total_size.emit(self.total_size // 1024)

        for count, (src, dest) in enumerate(self.src_dest_list, start=1):
            if not self.is_should_run():
                break
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            self.copied_count = count
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
            while True:
                buf = fsrc.read(block)
                if not buf:
                    break
                fdst.write(buf)
                self.copied_size += len(buf) // 1024
                if not self.is_should_run():
                    return
                while self.pause_flag:
                    QThread.msleep(100)

        shutil.copystat(src, dest, follow_symlinks=True)

    def toggle_pause_flag(self, value: bool):
        self.pause_flag = value


class RatingTask(URunnable):

    class Sigs(QObject):
        finished_ = pyqtSignal()

    def __init__(self, main_dir: str, data_item: DataItem, new_rating: int):
        super().__init__()
        self.data_item = data_item
        self.new_rating = new_rating
        self.main_dir = main_dir
        self.sigs = RatingTask.Sigs()

    def task(self):        
        conn = Dbase.get_conn(Dbase.engine)
        stmt = sqlalchemy.update(CACHE)
        if self.data_item.type_ == Static.folder_type:
            stmt = stmt.where(*DataItem.get_folder_conds(self.data_item))
        else:
            stmt = stmt.where(Clmns.partial_hash==self.data_item.partial_hash)
        stmt = stmt.values(rating=self.new_rating)
        Dbase.execute(conn, stmt)
        Dbase.commit(conn)
        Dbase.close_conn(conn)
        self.sigs.finished_.emit()


class SearchTask(URunnable):

    class Sigs(QObject):
        new_widget = pyqtSignal(DataItem)
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
        filename_lower = entry.name.lower()
        if self.text_lower in filename_lower:
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

        def insert(data_item: DataItem, img_array: np.ndarray):
            if Utils.write_thumb(data_item.thumb_path, img_array):
                stmt_list.append(DataItem.insert_file_stmt(data_item))
                if len(stmt_list) == stmt_limit:
                    execute_stmt_list(stmt_list)
                    stmt_list.clear()

        stmt_list: list = []
        stmt_limit = 10

        data_item = DataItem(entry.path)
        data_item.set_properties()
        if data_item.type_ != Static.folder_type:
            data_item.set_partial_hash()
        if entry.name.endswith(Static.img_exts):
            if os.path.exists(data_item.thumb_path):
                img_array = Utils.read_thumb(data_item.thumb_path)
            else:
                img_array = ReadImage.read_image(entry.path)
                img_array = SharedUtils.fit_image(img_array, Static.max_thumb_size)
                insert(data_item, img_array)
            qimage = Utils.qimage_from_array(img_array)
            data_item.qimages = {
                i: Utils.scaled(qimage, i)
                for i in Static.image_sizes
            }
            data_item.qimages.update({"src": qimage})
        self.sigs.new_widget.emit(data_item)
        QTest.qSleep(SearchTask.new_wid_sleep_ms)


class FinderItemsLoader(URunnable):

    class Sigs(QObject):
        finished_ = pyqtSignal(dict)

    hidden_syms: tuple[str] = ()
    sql_errors = (IntegrityError, OperationalError)

    def __init__(self, main_win_item: MainWinItem, sort_item: SortItem):
        """
        Вернет словарик
        {"path": str путь,  "data_items": [DataItem, DataItem, ...]
        """

        super().__init__()
        self.sigs = FinderItemsLoader.Sigs()
        self.sort_item = sort_item
        self.main_win_item = main_win_item

        self.finder_items: dict[str, DataItem] = {}
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
        items: list[DataItem] = []
        path_finder = PathFinder(self.main_win_item.main_dir)
        fixed_path = path_finder.get_result()

        if fixed_path is None:
            self.sigs.finished_.emit({"path": None, "data_items": items})
            return

        for i, path in enumerate(self._get_paths(fixed_path)):
            item = DataItem(path)
            item.set_properties()
            items.append(item)

        items = DataItem.sort_(items, self.sort_item)
        self.sigs.finished_.emit({"path": fixed_path, "data_items": items})

    def _get_paths(self, fixed_path: str):
        for entry in os.scandir(fixed_path):
            if entry.name.startswith(self.hidden_syms):
                continue
            if not os.access(entry.path, 4):
                print("tasks, finder items loader, get paths, access deined", entry.path)
                continue
            yield entry.path


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
        update_thumb = pyqtSignal(DataItem)
        set_loading = pyqtSignal(DataItem)
        finished_ = pyqtSignal()

    def __init__(self, main_win_item: MainWinItem, data_items: list[DataItem]):
        super().__init__()
        self.sigs = DbItemsLoader.Sigs()
        self.main_win_item = main_win_item
        self.data_items = data_items
        self.conn = Dbase.get_conn(Dbase.engine)
        self.corrupted_items: list[DataItem] = []

    def task(self):
        self.process_thumbs()
        Dbase.close_conn(self.conn)
        self.sigs.finished_.emit()

    def process_thumbs(self):
        self.data_items.sort(key=lambda x: x.size)
        stmt_list: list = []
        new_images: list[DataItem] = []
        exist_images: list[DataItem] = []
        svg_files: list[DataItem] = []
        exist_ratings: list[DataItem] = []

        for data_item in self.data_items:
            if not self.is_should_run():
                return
            if data_item.image_is_loaded:
                continue
            if data_item.filename.endswith((".svg", ".SVG")):
                svg_files.append(data_item)
            elif data_item.type_ == Static.folder_type:
                rating = self.get_item_rating(data_item)
                if rating is None:
                    stmt_list.append(DataItem.insert_folder_stmt(data_item))
                else:
                    data_item.rating = rating
                    stmt_list.append(DataItem.update_folder_stmt(data_item))
                    exist_ratings.append(data_item)
            else:
                data_item.set_partial_hash()
                rating = self.get_item_rating(data_item)
                if rating is None:
                    stmt_list.append(DataItem.insert_file_stmt(data_item))
                    if data_item.type_ in Static.img_exts:
                        new_images.append(data_item)
                else:
                    data_item.rating = rating
                    stmt_list.append(DataItem.update_file_stmt(data_item))
                    if data_item.type_ in Static.img_exts:
                        if data_item.thumb_path and os.path.exists(data_item.thumb_path):
                            exist_images.append(data_item)
                        else:
                            new_images.append(data_item)
                    else:
                        exist_ratings.append(data_item)

        self.execute_ratings(exist_ratings)
        self.execute_svg_files(svg_files)
        self.execute_exist_images(exist_images)
        self.execute_new_images(new_images)
        self.execute_stmt_list(stmt_list)
        self.execute_corrupted_images()
    
    def execute_stmt_list(self, stmt_list: list):
        for i in stmt_list:
            Dbase.execute(self.conn, i)
        Dbase.commit(self.conn)

    def execute_svg_files(self, svg_files: list[DataItem]):
        for i in svg_files:
            if not self.is_should_run():
                break
            qimage = Utils.render_svg(i.src, 512)
            i.qimages = {
                x: Utils.scaled(qimage, x)
                for x in Static.image_sizes
            }
            i.qimages.update({"src": qimage})
            self.update_thumb(i)

    def execute_ratings(self, exist_ratings: list[DataItem]):
        for i in exist_ratings:
            if not self.is_should_run():
                break
            self.update_thumb(i)

    def execute_exist_images(self, exist_images: list[DataItem]):
        for i in exist_images:
            if not self.is_should_run():
                break
            qimage = Utils.qimage_from_array(Utils.read_thumb(i.thumb_path))
            i.qimages = {
                i: Utils.scaled(qimage, i)
                for i in Static.image_sizes
            }
            i.qimages.update({"src": qimage})
            self.update_thumb(i)

    def execute_new_images(self, new_images: list[DataItem]):
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
                i.qimages = {
                    i: Utils.scaled(qimage, i)
                    for i in Static.image_sizes
                }
                i.qimages.update({"src": qimage})
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
                qimage = Utils.qimage_from_array(img)
                i.qimages = {
                    i: Utils.scaled(qimage, i)
                    for i in Static.image_sizes
                }
                i.qimages.update({"src": qimage})
                Utils.write_thumb(i.thumb_path, img)
                self.update_thumb(i)
            if not new_corrupted:
                break
            self.corrupted_items = new_corrupted
            QThread.msleep(ms)

    def update_thumb(self, thumb: DataItem):
        try:
            self.sigs.update_thumb.emit(thumb)
        except RuntimeError as e:
            self.set_should_run(False)
            print("tasks, LoadImagesTask update_thumb.emit error", e)
    
    def set_loading_thumb(self, thumb: DataItem):
        try:
            self.sigs.set_loading.emit(thumb)
        except RuntimeError as e:
            self.set_should_run(False)
            print("tasks, LoadImagesTask set_loading.emit error", e)

    def get_item_rating(self, data_item: DataItem) -> bool:
        stmt = sqlalchemy.select(Clmns.rating)
        if data_item.type_ == Static.folder_type:
            stmt = stmt.where(*DataItem.get_folder_conds(data_item))
        else:
            stmt = stmt.where(Clmns.partial_hash==data_item.partial_hash)
        res = Dbase.execute(self.conn, stmt).scalar()
        return res
    

class ReadImg(URunnable):

    class Sigs(QObject):
        finished_ = pyqtSignal(tuple)

    cache_limit = 15
    cached_images: dict[str, QImage] = {}

    def __init__(self, src: str, desaturate: bool = True):
        super().__init__()
        self.desaturate = desaturate
        self.sigs = ReadImg.Sigs()
        self.src: str = src

    def task(self):
        if self.src not in self.cached_images:
            img_array = ReadImage.read_image(self.src)
            if self.desaturate:
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

    def task(self):
        subprocess.run(
            [
                "osascript",
                os.path.join(Static.internal_scpt_dir, "remove_files.scpt")
            ] + self.urls)
        self.sigs.finished_.emit()


class PathFixer(URunnable):

    class Sigs(QObject):
        finished_ = pyqtSignal(tuple)

    def __init__(self, path: str):
        """
        PathFixed.sigs.finished_ -> (fixed path, bool os.path.isdir)
        """
        super().__init__()
        self.path = path
        self.path_finder = PathFinder(path)
        self.sigs = PathFixer.Sigs()

    def task(self):
        if os.path.exists(self.path):
            result = (self.path, os.path.isdir(self.path))
        else:
            fixed_path = self.path_finder.get_result()
            if fixed_path is not None:
                result = (fixed_path, os.path.isdir(fixed_path))
            else:
                result = (None, None)
        self.sigs.finished_.emit(result)


class ToJpegConverter(URunnable):

    class Sigs(QObject):
        finished_ = pyqtSignal(list)

    def __init__(self, urls: list[str]):
        super().__init__()
        self.urls = urls
        self.new_urls: list[str] = []
        self.sigs = ToJpegConverter.Sigs()
        self.total_count = 0
        self.current_count = 0
        self.current_filename = ""

    def task(self):
        urls = [i for i in self.urls if i.endswith(Static.img_exts)]
        urls.sort(key=lambda p: os.path.getsize(p))
        self.total_count = len(urls)
        for x, url in enumerate(urls, start=1):
            save_path = self._save_jpg(url)
            if save_path:
                self.new_urls.append(save_path)
            self.current_count = x
            self.current_filename = os.path.basename(url)
        self.sigs.finished_.emit(self.new_urls)

    def _save_jpg(self, src: str) -> None:
        try:
            img_array = ReadImage.read_image(src)
            img = Image.fromarray(img_array.astype(np.uint8))
            img = img.convert("RGB")
            save_path = os.path.splitext(src)[0] + ".jpg"
            img.save(save_path, format="JPEG", quality=99)
            return save_path
        except Exception:
            Utils.print_error()
            return None


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
        total_count = pyqtSignal(int)
        finished_ = pyqtSignal()

    def __init__(self, dirs: list[str]):
        super().__init__()
        self.dirs = dirs
        self.sigs = CacheDownloader.Sigs()
        self.conn = Dbase.get_conn(Dbase.engine)
        self.current_filename = ""
        self.current_count = 0

    def task(self):
        try:
            self._task()
        except Exception as e:
            import traceback
            print(traceback.format_exc())

        self.sigs.finished_.emit()
        Dbase.close_conn(self.conn)

    def _task(self):
        new_images = self.prepare_images()
        stmt_list = []
        stmt_limit = 10

        self.sigs.total_count.emit(len(new_images))
        for x, data in enumerate(new_images, start=1):
            if not self.is_should_run():
                if stmt_list:
                    self.execute_stmt_list(stmt_list)
                return
            data_item: DataItem = data["data_item"]
            self.current_count = x
            self.current_filename = data_item.filename
            if self.write_thumb(data_item):
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
        new_images: list[dict[DataItem, str]] = []
        stack = [*self.dirs]

        while stack:
            last_dir = stack.pop()
            for i in os.scandir(last_dir):
                if not self.is_should_run():
                    return new_images
                if i.is_dir():
                    stack.append(i.path)
                elif i.name.endswith(Static.img_exts):
                    data_item = DataItem(i.path)
                    data_item.set_properties()
                    data_item.set_partial_hash()
                    if self.exists_check(data_item) is None:
                        new_images.append({
                            "data_item": data_item,
                            "stmt": DataItem.insert_file_stmt(data_item)
                        })
        return new_images

    def exists_check(self, data_item: DataItem):
        stmt = (
            sqlalchemy.select(Clmns.id)
            .where(Clmns.partial_hash == data_item.partial_hash)
        )
        return Dbase.execute(self.conn, stmt).scalar() or None
    
    def cut_filename(self, text: str, limit: int = 25):
        if len(text) > limit:
            return text[:limit] + "..."
        return text

    def write_thumb(self, data_item: DataItem):
        img = ReadImage.read_image(data_item.src)
        img = SharedUtils.fit_image(img, Static.max_thumb_size)
        return Utils.write_thumb(data_item.thumb_path, img)
    


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

    def __init__(self, items: list[DataItem]):
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

    def get_folder_size(self, data_item: DataItem):
        stack = [data_item.src]
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

    def __init__(self, data_item: DataItem):
        super().__init__()
        self.data_item = data_item
        self.signals = FileInfo.Sigs()

    def task(self) -> dict[str, str| int]:
        if self.data_item.type_ == Static.folder_type:
            size_ = self.calculating
            type_ = self.ru_folder
        else:
            size_ = SharedUtils.get_f_size(self.data_item.size)
            type_ = self.data_item.type_
        
        name = self.lined_text(self.data_item.filename)
        src = self.lined_text(self.data_item.src)
        mod = SharedUtils.get_f_date(self.data_item.mod)

        data = {
            FileInfo.name_text: name,
            FileInfo.type_text: type_,
            FileInfo.mod_text: mod,
            FileInfo.src_text: src,
            FileInfo.size_text: size_,
            }
        
        if self.data_item.type_ != Static.folder_type:
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


class DirWatcher(QThread):
    changed = pyqtSignal(object)

    def __init__(self, path: str):
        super().__init__()
        self.path = path
        self._running = True

    def stop(self):
        self._running = False

    def wait_dir(self):
        while self._running and not os.path.exists(self.path):
            self.msleep(1000)

    def run(self):
        if self.path is None:
            return

        self.wait_dir()
        if not self._running:
            return

        observer = Observer()
        handler = _DirChangedHandler(
            lambda e: self.changed.emit(e)
        )
        observer.schedule(handler, self.path, recursive=False)
        observer.start()

        try:
            while self._running:
                self.msleep(1000)
                if not os.path.exists(self.path):
                    observer.stop()
                    observer.join()
                    self.wait_dir()
                    if not self._running:
                        return
                    observer = Observer()
                    observer.schedule(handler, self.path, recursive=False)
                    observer.start()
        finally:
            observer.stop()
            observer.join()


class OnStartTask(URunnable):

    class Sigs(QObject):
        finished_ = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.sigs = OnStartTask.Sigs()

    def task(self):
        self.make_all_dirs()
        self.set_Macintosh_HD()
        self.remove_old_files()
        self.copy_uti_icons()
        self.load_uti_icons_to_ram()
        self.load_image_apps()
        self.sigs.finished_.emit()

    def make_all_dirs(self):
        dirs = (
            Static.app_dir,
            Static.external_thumbs_dir,
            Static.external_uti_dir
        )
        for i in dirs:
            os.makedirs(i, exist_ok=True)

    def copy_uti_icons(self):
        uti_folder = "./uti_icons"
        uti_json = os.path.join(uti_folder, "uti_icons.json")
        uti_zip = os.path.join(uti_folder, "uti_icons.zip")

        with open(uti_json) as file:
            internal_uti_icons = json.load(file)
        external_uti_icons = [i for i in os.listdir(Static.external_uti_dir)]
        for i in internal_uti_icons:
            if i not in external_uti_icons:
                external_zip = shutil.copy2(uti_zip, Static.app_dir)
                shutil.rmtree(Static.external_uti_dir)
                try:
                    with zipfile.ZipFile(external_zip, "r") as zip_ref:
                        zip_ref.extractall(Static.app_dir)
                except zipfile.BadZipFile:
                    print("download uti_icons.zip and place to ./uti_icons")
                    print("https://disk.yandex.ru/d/RNqZ9xCFHiDONQ")
                    SharedUtils.exit_force()
                break

    def load_uti_icons_to_ram(self):
        for entry in os.scandir(Static.external_uti_dir):
            if entry.is_file() and entry.name.endswith(".png"):
                uti_filetype = entry.name.rsplit(".png", 1)[0]
                qimage = QImage(entry.path)
                Dynamic.uti_data[uti_filetype] = {}
                for i in Static.image_sizes:
                    resized_qimage = Utils.scaled(qimage, i)
                    Dynamic.uti_data[uti_filetype][i] = resized_qimage

    def load_image_apps(self):
        patterns = [
            "/Applications/Adobe Photoshop*/*.app",
            "/Applications/Adobe Photoshop*.app",
            "/Applications/Capture One*/*.app",
            "/Applications/Capture One*.app",
            "/Applications/ImageOptim.app",
            "/System/Applications/Preview.app",
            "/System/Applications/Photos.app",
        ]

        apps = []
        for pat in patterns:
            for path in glob.glob(pat):
                if path not in apps:
                    apps.append(path)

        apps.sort(key=os.path.basename)
        Dynamic.image_apps = apps

    def set_Macintosh_HD(self):
        app_support = os.path.expanduser('~/Library/Application Support')
        volumes = "/Volumes"
        for i in os.scandir(volumes):
            if not os.path.ismount(i.path):
                if os.path.exists(i.path + app_support):
                    Dynamic.sys_vol = i.path

    def remove_old_files(self):
        files = (
            "cfg.json",
            "db.db",
            "uti_icons",
            "log.txt",
            "servers.json",
            "thumbnails"
        )

        for i in os.scandir(Static.app_dir):
            if i.name not in files:
                try:
                    if i.is_file():
                        os.remove(i.path)
                    else:
                        shutil.rmtree(i.path)
                except Exception as e:
                    print("cfg, do before start, error remove dir", e)


class AnyTaskLoader(URunnable):
    
    class Sigs(QObject):
        finished_ = pyqtSignal(bool)

    def __init__(self, cmd: callable):
        super().__init__()
        self.sigs = AnyTaskLoader.Sigs()
        self.cmd = cmd

    def task(self):
        try:
            self.cmd()
            self.sigs.finished_.emit(1)
        except Exception as e:
            print("Any task loader error", e)
            self.sigs.finished_.emit(0)