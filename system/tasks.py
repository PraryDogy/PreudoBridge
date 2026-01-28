import difflib
import gc
import glob
import json
import os
import shutil
import subprocess
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


class RevealFiles(URunnable):
    def __init__(self,  urls: list[str]):
        super().__init__()
        self.urls = urls

    def task(self):
        subprocess.run(
            [
                "osascript",
                os.path.join(Static.internal_scpt_dir, "reveal_files.scpt")
            ] + self.urls)


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
        # volumes = [i.path for i in os.scandir("/Volumes")]
        # Dynamic.sys_vol = volumes[0]
        Dynamic.sys_vol = "/Volumes/Macintosh HD"

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