import os

import sqlalchemy
from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtWidgets import QLabel, QWidget
from sqlalchemy.exc import IntegrityError, OperationalError

from cfg import Dynamic, Static
from database import CACHE, Dbase
from utils import URunnable, Utils

from ._base_widgets import BaseItem

LOADING_T = "Загрузка..."
SQL_ERRORS = (IntegrityError, OperationalError)


class WorkerSignals(QObject):
    finished_ = pyqtSignal(tuple)


class FinderItems(URunnable):
    def __init__(self, main_dir: str):
        super().__init__()
        self.signals_ = WorkerSignals()
        self.main_dir = main_dir

    @URunnable.set_running_state
    def run(self):
        try:
            base_items = self.get_base_items()
            conn = self.create_connection()
            if conn:
                base_items, new_items = self.set_rating(conn, base_items)
            else:
                base_items, new_items = self.get_items_no_db()
        except SQL_ERRORS as e:
            print(e)
            base_items, new_items = self.get_items_no_db()
        except Exception as e:
            print(e)
            base_items, new_items = [], []

        base_items = BaseItem.sort_items(base_items)
        new_items = BaseItem.sort_items(new_items)
        self.signals_.finished_.emit((base_items, new_items))

    def create_connection(self) -> sqlalchemy.Connection | None:
        db = os.path.join(self.main_dir, Static.DB_FILENAME)
        dbase = Dbase()
        engine = dbase.create_engine(path=db)
        if engine is None:
            return None
        else:
            return engine.connect()

    def set_rating(self, conn: sqlalchemy.Connection, base_items: list[BaseItem]):
        Dynamic.busy_db = True
        q = sqlalchemy.select(CACHE.c.name, CACHE.c.rating)
        res = conn.execute(q).fetchall()
        res = {
            name: rating
            for name, rating in res
        }
        Dynamic.busy_db = False
        new_files = []
        for i in base_items:
            name = Utils.get_hash_filename(filename=i.name)
            if name in res:
                i.rating = res.get(name)
            else:
                new_files.append(i)

        return base_items, new_files

    def get_base_items(self) -> list[BaseItem]:
        base_items: list[BaseItem] = []
        with os.scandir(self.main_dir) as entries:
            for entry in entries:
                if entry.name.startswith("."):
                    continue
                item = BaseItem(entry.path)
                item.setup()
                base_items.append(item)
        return base_items

    def get_items_no_db(self):
        base_items = []
        with os.scandir(self.main_dir) as entries:
            for entry in entries:
                if entry.name.startswith("."):
                    continue
                if entry.is_dir() or entry.name.endswith(Static.IMG_EXT):
                    item = BaseItem(entry.path)
                    item.setup()
                    base_items.append(item)
        return base_items, []


class LoadingWid(QLabel):
    def __init__(self, parent: QWidget):
        super().__init__(text=LOADING_T, parent=parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            f"""
                background: {Static.GRAY_GLOBAL};
                border-radius: 4px;
            """
        )

    def center(self, parent: QWidget):
        geo = self.geometry()
        geo.moveCenter(parent.geometry().center())
        self.setGeometry(geo)