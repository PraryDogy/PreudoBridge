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


class DirScaner(URunnable):

    class Sigs(QObject):
        finished_ = pyqtSignal(dict)

    def __init__(self, main_win_item: MainWinItem, sort_item: SortItem, show_hidden: bool):
        """
        Возвращает через сигнал:
        - {"path": путь директории, "data_items": список DataItem}
        """

        super().__init__()
        self.sigs = DirScaner.Sigs()
        self.main_win_item = main_win_item
        self.sort_item = sort_item
        self.show_hidden = show_hidden

    def task(self):
        try:
            self.task_()
        except Exception as e:
            self.sigs.finished_.emit({"path": None, "data_items": []})

    def task_(self):
        items = []
        hidden_syms = () if self.show_hidden else Static.hidden_symbols

        fixed_path = PathFinder(self.main_win_item.main_dir).get_result()
        if fixed_path is None:
            self.sigs.finished_.emit({"path": None, "data_items": []})
            return

        for entry in os.scandir(fixed_path):
            if entry.name.startswith(hidden_syms):
                continue
            if not os.access(entry.path, 4):
                continue

            item = DataItem(entry.path)
            item.set_properties()
            items.append(item)

        items = DataItem.sort_(items, self.sort_item)
        self.sigs.finished_.emit({"path": fixed_path, "data_items": items})

    def terminate(self):
        """
        Метод заглушка аналогично multiprocessing.Process.terminate()
        """
        ...