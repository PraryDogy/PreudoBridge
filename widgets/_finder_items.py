import os

import sqlalchemy
from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QLabel, QWidget

from cfg import JsonData, Static
from database import CACHE, ColumnNames, Dbase, OrderItem
from utils import URunnable, Utils

LOADING_T = "Загрузка..."


class WorkerSignals(QObject):
    finished_ = pyqtSignal(list)


class FinderItems(URunnable):
    def __init__(self):
        super().__init__()
        self.signals_ = WorkerSignals()
        self.order_items: list[OrderItem] = []

        db = os.path.join(JsonData.root, Static.DB_FILENAME)
        self.engine = Dbase().create_engine(path=db)

    @URunnable.set_running_state
    def run(self):

        try:

            self.get_items(
                db_ratings=self.get_rating()
            )

            self.order_items = OrderItem.order_items(
                order_items=self.order_items
            )

            self.signals_.finished_.emit(self.order_items)

        except (PermissionError, FileNotFoundError, NotADirectoryError) as e:
            self.order_items = []
            self.signals_.finished_.emit(self.order_items)
        
        except RuntimeError as e:
            ...

    def get_rating(self):

        q = sqlalchemy.select(CACHE.c.name, CACHE.c.rating)

        with self.engine.connect() as conn:

            res = conn.execute(q).fetchall()

            return {
                name: rating
                for name, rating in res
            }

    def get_items(self, db_ratings: dict) -> list[OrderItem]:

        with os.scandir(JsonData.root) as entries:

            for entry in entries:

                if entry.name.startswith("."):
                    continue

                if entry.is_dir() or entry.name.endswith(Static.IMG_EXT):
                    try:
                        stats = entry.stat()
                    except Exception:
                        continue

                    size = stats.st_size
                    mod = stats.st_mtime

                    db_rating = db_ratings.get(entry.name)
                    rating = 0 if db_rating is None else db_rating

                    item = OrderItem(entry.path, size, mod, rating)
                    self.order_items.append(item)


class LoadingWid(QLabel):
    def __init__(self, parent: QWidget):
        super().__init__(text=LOADING_T, parent=parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            f"""
                background: {Static.GRAY_UP_BTN};
                border-radius: 4px;
            """
        )