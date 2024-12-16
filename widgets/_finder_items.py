import os

import sqlalchemy
from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QLabel, QWidget

from cfg import JsonData, Static
from database import CACHE, Dbase, OrderItem
from utils import URunnable, Utils

LOADING_T = "Загрузка..."


class ImageData:
    __slots__ = ["src", "pixmap"]

    def __init__(self, src: str, pixmap: QPixmap):
        self.src: str = src
        self.pixmap: QPixmap = pixmap


class WorkerSignals(QObject):
    finished_ = pyqtSignal(list)


class FinderItems(URunnable):
    def __init__(self):
        super().__init__()
        self.signals_ = WorkerSignals()
        self.db_color_rating: dict[str, list] = {}
        self.order_items: list[OrderItem] = []

    @URunnable.set_running_state
    def run(self):
        try:
            self.get_color_rating()
            self.get_items()
            self.order_items = OrderItem.order_items(self.order_items)

        except (PermissionError, FileNotFoundError, NotADirectoryError) as e:
            Utils.print_error(self, e)
            self.order_items = []
        
        except RuntimeError as e:
            Utils.print_error(parent=None, error=e)

        self.signals_.finished_.emit(self.order_items)

    def get_color_rating(self):
        q = sqlalchemy.select(CACHE.c.src, CACHE.c.colors, CACHE.c.rating)
        q = q.where(CACHE.c.root == JsonData.root)
  
        with Dbase.engine.connect() as conn:
            res = conn.execute(q).fetchall()

            self.db_color_rating = {
                src: [colors, rating]
                for src, colors, rating in res
            }

    def get_items(self) -> list:

        with os.scandir(JsonData.root) as entries:

            for entry in entries:

                if entry.name.startswith("."):
                    continue

                if entry.is_dir() or entry.name.endswith(Static.IMG_EXT):
                    try:
                        stats = entry.stat()
                    except (PermissionError, FileNotFoundError, OSError):
                        continue

                    size = stats.st_size
                    mod = stats.st_mtime
                    colors = ""
                    rating = 0

                    db_item = self.db_color_rating.get(entry.path)

                    if db_item:
                        colors, rating = db_item

                    item = OrderItem(entry.path, size, mod, colors, rating)
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