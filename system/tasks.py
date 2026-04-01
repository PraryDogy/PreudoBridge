import gc
import glob
import json
import os
import shutil
import subprocess
import traceback
import zipfile

import numpy as np
import sqlalchemy
from PyQt5.QtCore import QObject, QRunnable, QThreadPool, QTimer, pyqtSignal
from PyQt5.QtGui import QImage

from cfg import Dynamic, Static
from system.shared_utils import ImgUtils, SharedUtils

from .database import CacheTable, Dbase
from .items import DataItem, DirItem
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
        with Dbase.main_engine.begin() as conn:
            stmt = (
                sqlalchemy.update(CacheTable.table)
                .values(rating=self.new_rating)
            )
            if self.data_item.type_ == Static.folder_type:
                stmt = stmt.where(*DataItem.get_folder_conds(self.data_item))
            else:
                stmt = stmt.where(CacheTable.partial_hash==self.data_item.partial_hash)
            conn.execute(stmt)
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
            self.sigs.finished_.emit(self.get_hashdir_size())
        except Exception as e:
            print("tasks, DataSize error", e)

    def get_hashdir_size(self):
        total = 0
        count = 0
        stack = [Static.external_thumbs_dir]
        while stack:
            current = stack.pop()
            for i in os.scandir(current):
                if i.is_dir():
                    stack.append(i.path)
                elif i.name.endswith(ImgUtils.ext_all):
                    total += os.path.getsize(i.path)
                    count += 1
        return {"total": total, "count": count}


class CacheCleaner(URunnable):

    class Sigs(QObject):
        finished_ = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.sigs = CacheCleaner.Sigs()

    def task(self):
        try:
            thumb_paths, non_exist_paths = self.get_thumb_paths()
            if thumb_paths:
                removed_thumbs = self.remove_thumbs(thumb_paths)
                self.remove_rows(removed_thumbs)
            if non_exist_paths:
                self.remove_non_exist(non_exist_paths)
        except Exception as e:
            print("tasks, ClearData error", e)
        self.sigs.finished_.emit()

    def get_thumb_paths(self):
        thumb_paths = set()
        non_exist_paths = set()
        with Dbase.main_engine.connect() as conn:
            stmt = (
                sqlalchemy.select(CacheTable.thumb_path)
                .where(
                    CacheTable.rating == 0,
                    CacheTable.thumb_path.isnot(None),
                    CacheTable.thumb_path != ""
                )
            )
            rows = conn.execute(stmt).scalars().all()
            for thumb_path in rows:
                if os.path.exists(thumb_path):
                    thumb_paths.add(thumb_path)
                else:
                    non_exist_paths.add(thumb_path)
        return thumb_paths, non_exist_paths
    
    def remove_thumbs(self, thumb_paths: set):
        removed_thumbs = set()
        for i in thumb_paths:
            try:
                os.remove(i)
                removed_thumbs.add(i)
            except Exception as e:
                print("Cache cleaner remove thumb error")
            try:
                os.rmdir(os.path.dirname(i))
            except OSError:
                pass
        return removed_thumbs

    def remove_rows(self, removed_thumbs: set):
        with Dbase.main_engine.begin() as conn:
            stmt = (
                sqlalchemy.delete(CacheTable.table)
                .where(CacheTable.thumb_path.in_(removed_thumbs))
            )
            conn.execute(stmt)

    def remove_non_exist(self, non_exist_paths: set[str]):
        with Dbase.main_engine.begin() as conn:
            stmt = (
                sqlalchemy.delete(CacheTable.table)
                .where(CacheTable.thumb_path.in_(
                    non_exist_paths
                ))
            )
            conn.execute(stmt)


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
        finished_ = pyqtSignal(DirItem)

    def __init__(self, dir_item: DirItem):
        super().__init__()
        self.sigs = DirScaner.Sigs()
        self.dir_item =  dir_item

    def task(self):
        try:
            self.task_()
        except Exception as e:
            self.sigs.finished_.emit(self.dir_item)

    def task_(self):
        hidden_syms = () if self.dir_item._show_hidden else Static.hidden_symbols

        for entry in os.scandir(self.dir_item._main_win_item.main_dir):
            if entry.name.startswith(hidden_syms):
                continue
            if not os.access(entry.path, 4):
                continue

            item = DataItem(entry.path)
            item.set_properties()
            self.dir_item.data_items.append(item)

        self.dir_item.data_items = DataItem.sort_(self.dir_item.data_items, self.dir_item._sort_item)
        self.sigs.finished_.emit(self.dir_item)

    def terminate_join(self):
        """
        Метод заглушка аналогично multiprocessing.Process.terminate()
        """
        ...


class ImgArrayQImage(URunnable):
    
    class Sigs(QObject):
        finished_ = pyqtSignal(QImage)

    def __init__(self, img_array: np.ndarray):
        super().__init__()
        self.sigs = ImgArrayQImage.Sigs()
        self.img_array = img_array

    def task(self):
        self.sigs.finished_.emit(
            Utils.qimage_from_array(self.img_array)
        )