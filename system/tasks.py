import gc
import glob
import json
import os
import shutil
import subprocess
import traceback

import numpy as np
import sqlalchemy
from PyQt5.QtCore import QObject, QRunnable, QThreadPool, QTimer, pyqtSignal
from PyQt5.QtGui import QImage

from cfg import Dynamic, Static
from system.shared_utils import ImgUtils

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
        shutil.rmtree(Static.external_thumbs_dir)
        os.remove(Static.external_db)
        os.makedirs(Static.external_thumbs_dir)
        with open(Static.external_db, "w"):
            pass
        Dbase.init()
        self.sigs.finished_.emit()



class OnStartTask(URunnable):

    class Sigs(QObject):
        finished_ = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.sigs = OnStartTask.Sigs()

    def task(self):
        self.make_all_dirs()
        self.remove_old_files()
        self.load_image_apps()
        self.sigs.finished_.emit()

    def make_all_dirs(self):
        dirs = (
            Static.app_dir,
            Static.external_thumbs_dir
        )
        for i in dirs:
            os.makedirs(i, exist_ok=True)

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

    def remove_old_files(self):
        files = (
            "cfg.json",
            "db.db",
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
            print(traceback.format_exc())
            self.sigs.finished_.emit(self.dir_item)

    def task_(self):
        for entry in os.scandir(self.dir_item.main_win_item.abs_current_dir):
            if entry.name.startswith(Static.hidden_symbols):
                continue
            if not os.access(entry.path, 4):
                continue
            if entry.is_dir() or entry.name.endswith(ImgUtils.ext_all):
                item = DataItem(entry.path)
                item.set_properties()
                self.dir_item.data_items.append(item)

        self.dir_item.data_items = DataItem.sort_(
            data_items=self.dir_item.data_items,
            sort_item=self.dir_item._sort_item
        )

        self.remove_items()
        self.sigs.finished_.emit(self.dir_item)

    def remove_items(self):
        finder_items = {
            (i.filename, i.mod, i.size): i
            for i in self.dir_item.data_items
        }
        with Dbase.main_engine.connect() as conn:
            clmns = (
                CacheTable.filename,
                CacheTable.mod,
                CacheTable.size,
                CacheTable.thumb_path
            )
            stmt = (
                sqlalchemy.select(*clmns)
                .where(CacheTable.rel_parent==self.dir_item.main_win_item.rel_parent)
                .where(CacheTable.fs_id==self.dir_item.main_win_item.fs_id)
            )
            db_items = {
                (filename, mod, size): thumb_path
                for filename, mod, size, thumb_path in conn.execute(stmt)
            }

        thumb_paths = set()
        for i in db_items:
            if i not in finder_items:
                thumb_paths.add(db_items[i])

        ok_thumb_paths = set()
        for i in thumb_paths:
            try:
                os.remove(i)
                ok_thumb_paths.add(i)
            except Exception as e:
                print("system > tasks > DirScaner > remove thumb error", e)
                continue
            try:
                os.rmdir(os.path.dirname(i))
            except OSError:
                pass
        
        if not ok_thumb_paths:
            return

        with Dbase.main_engine.begin() as conn:
            stmt = (
                sqlalchemy.delete(CacheTable.table)
                .where(CacheTable.fs_id==self.dir_item.main_win_item.fs_id)
                .where(CacheTable.rel_parent==self.dir_item.main_win_item.rel_parent)
                .where(CacheTable.thumb_path.in_(ok_thumb_paths))
            )
            conn.execute(stmt)


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