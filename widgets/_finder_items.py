import os

import sqlalchemy
from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtWidgets import QLabel, QWidget
from sqlalchemy.exc import IntegrityError, OperationalError

from cfg import JsonData, Static, Dynamic
from database import CACHE, Dbase, OrderItem
from utils import URunnable, Utils

LOADING_T = "Загрузка..."
SQL_ERRORS = (IntegrityError, OperationalError)


class WorkerSignals(QObject):
    finished_ = pyqtSignal(tuple)


class FinderItems(URunnable):
    def __init__(self):
        super().__init__()
        self.signals_ = WorkerSignals()

    @URunnable.set_running_state
    def run(self):

        try:
            order_items = self.get_order_items()
            conn = self.create_connection()
            if conn:
                order_items, new_items = self.set_rating(order_items=order_items)
            else:
                order_items, new_items = self.get_items_no_db()
            order_items = OrderItem.sort_items(order_items=order_items)
            self.signals_.finished_.emit((order_items, new_items))
        except SQL_ERRORS as e:
            print(e)
            order_items, new_items = self.get_items_no_db()
            order_items = OrderItem.sort_items(order_items=order_items)
            self.signals_.finished_.emit((order_items, new_items))
        except Exception as e:
            print(e)
            order_items, new_items = [], []
            self.signals_.finished_.emit((order_items, new_items))

    def create_connection(self) -> sqlalchemy.Connection | None:
        db = os.path.join(JsonData.root, Static.DB_FILENAME)
        dbase = Dbase()
        engine = dbase.create_engine(path=db)
        if engine is None:
            return None
        else:
            return engine.connect()

    def set_rating(self, conn: sqlalchemy.Connection, order_items: list[OrderItem]):
        Dynamic.busy_db = True
        q = sqlalchemy.select(CACHE.c.name, CACHE.c.rating)
        res = conn.execute(q).fetchall()
        res = {
            name: rating
            for name, rating in res
        }
        Dynamic.busy_db = False
        new_files = []
        for i in order_items:
            name = Utils.hash_filename(filename=i.name)
            if name in res:
                i.rating = res.get(name)
            else:
                new_files.append(i)

        return order_items, new_files

    def get_order_items(self) -> list[OrderItem]:
        order_items: list[OrderItem] = []
        with os.scandir(JsonData.root) as entries:
            for entry in entries:
                if entry.name.startswith("."):
                    continue
                try:
                    stats = entry.stat()
                except Exception:
                    continue
                size = stats.st_size
                mod = stats.st_mtime
                item = OrderItem(entry.path, size, mod, 0)
                order_items.append(item)
        return order_items

    def get_items_no_db(self):
        order_items = []
        with os.scandir(JsonData.root) as entries:
            for entry in entries:
                if entry.name.startswith("."):
                    continue
                if entry.is_dir() or entry.name.endswith(Static.IMG_EXT):
                    item = OrderItem(entry.path, 0, 0, 0)
                    order_items.append(item)
        return order_items, []


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