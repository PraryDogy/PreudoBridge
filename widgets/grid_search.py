import os
from ast import literal_eval
from time import sleep

import sqlalchemy
from numpy import ndarray
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QCloseEvent, QPixmap
from sqlalchemy.exc import IntegrityError, OperationalError

from cfg import IMG_EXT, MAX_SIZE, JsonData
from database import CACHE, Dbase
from fit_img import FitImg
from signals import SignalsApp
from utils import QObject, Threads, URunnable, Utils

from ._grid import Grid
from ._thumb import ThumbSearch

SLEEP = 0.1


class WidgetData:
    __slots__ = ["src", "colors", "rating", "size", "mod", "pixmap"]

    def __init__(self, src: str, colors: str, rating: int, size: int, mod: int, pixmap: QPixmap):
        self.src: str = src
        self.colors: str = colors
        self.rating: int = rating
        self.size: int = size
        self.mod: int = mod
        self.pixmap: QPixmap = pixmap


class WorkerSignals(QObject):
    add_new_widget = pyqtSignal(WidgetData)


class SearchFinder(URunnable):
    def __init__(self, search_text: str):
        super().__init__()

        self.worker_signals = WorkerSignals()

        self.search_text: str = search_text
        self.conn: sqlalchemy.Connection = Dbase.engine.connect()
        self.insert_count: int = 0 
        self.pixmap_img = QPixmap("images/file_210.png")

    def run(self):
        self.set_is_running(True)

        try:
            self.search_text: tuple = literal_eval(self.search_text)
        except (ValueError, SyntaxError):
            pass

        if isinstance(self.search_text, tuple):
            setattr(self, "is_tuple", True)

        elif isinstance(self.search_text, int):
            self.search_text = str(self.search_text)

        for root, _, files in os.walk(JsonData.root):
            if not self.is_should_run():
                break

            for file in files:
                if not self.is_should_run():
                    break

                print(root, file)

                file_path: str = os.path.join(root, file)
                file_path_lower: str = file_path.lower()


                if file_path_lower.endswith(IMG_EXT):
                                        
                    if hasattr(self, "is_tuple"):
                        if file_path_lower.endswith(self.search_text):
                            self.create_wid(file_path)


                    elif self.search_text in file:
                        self.create_wid(file_path)

        if self.insert_count > 0:
            try:
                self.conn.commit()
            except (IntegrityError, OperationalError) as e:
                Utils.print_error(self, e)

        self.conn.close()

        if self.is_should_run():
            SignalsApp.all.search_finished.emit(str(self.search_text))

        self.set_is_running(False)

    def create_wid(self, src: str):
        try:
            stats = os.stat(src)
            size = stats.st_size
            mod = stats.st_mtime
        except (PermissionError, FileNotFoundError) as e:
            Utils.print_error(self, e)
            return None

        pixmap: QPixmap = None
        colors: str = ""
        rating: int = 0

        db_data: dict = self.get_img_data_db(src)

        if isinstance(db_data, dict):
            img = Utils.read_image_hash(db_data.get("hash"))
            pixmap: QPixmap = Utils.pixmap_from_array(img)
            colors = db_data.get("colors")
            rating = db_data.get("rating")

        else:
            img_array: ndarray = self.create_img_array(src)

            self.img_data_to_db(src, img_array, size, mod)

            if isinstance(img_array, ndarray):
                pixmap = Utils.pixmap_from_array(img_array)

        if not pixmap:
            pixmap = self.pixmap_img

        self.worker_signals.add_new_widget.emit(
            WidgetData(src, colors, rating, size, mod, pixmap)
            )

        sleep(SLEEP)

    def get_img_data_db(self, src: str) -> dict | None:
        try:
            sel_stmt = sqlalchemy.select(CACHE.c.hash_path, CACHE.c.colors, CACHE.c.rating).where(CACHE.c.src == src)
            res = self.conn.execute(sel_stmt).first()

            if res:
                return {"hash": res[0], "colors": res[1], "rating": res[2]}
            else:
                return None

        except OperationalError as e:
            Utils.print_error(self, e)
            return None

    def img_data_to_db(self, src: str, img_array, size: int, mod: int):

        src = os.sep + src.strip().strip(os.sep)
        name = os.path.basename(src)
        type_ = os.path.splitext(name)[-1]
        hashed_path = Utils.get_hash_path(src)

        try:
            insert_stmt = sqlalchemy.insert(CACHE)
            insert_stmt = insert_stmt.values(
                src=src,
                hash_path=hashed_path,
                root=os.path.dirname(src),
                catalog="",
                name=name,
                type_=type_,
                size=size,
                mod=mod,
                colors="",
                rating=0
                )

            self.conn.execute(insert_stmt)

            self.insert_count += 1
            if self.insert_count >= 10:
                self.conn.commit()
                self.insert_count = 0

            Utils.write_image_hash(output_path=hashed_path, array_img=img_array)

        except (OperationalError, IntegrityError) as e:
            Utils.print_error(self, e)

    def create_img_array(self, src: str) -> ndarray | None:
        img = Utils.read_image(src)
        img = FitImg.start(img, MAX_SIZE)
        return img


class GridSearch(Grid):
    def __init__(self, width: int, search_text: str):
        super().__init__(width)

        self.col_count = Utils.get_clmn_count(width)
        self.row, self.col = 0, 0

        SignalsApp.all.create_path_labels.emit(JsonData.root, 0)

        self.task_ = SearchFinder(search_text)
        self.task_.worker_signals.add_new_widget.connect(self.add_new_widget)
        Threads.pool.start(self.task_)

    def add_new_widget(self, widget_data: WidgetData):
        wid = ThumbSearch(
            src=widget_data.src,
            size=widget_data.size,
            mod=widget_data.mod,
            colors=widget_data.colors,
            rating=widget_data.rating,
            pixmap=widget_data.pixmap,
            )

        wid.select.connect(lambda w=wid: self.select_new_widget(w))
        wid.open_in_view.connect(lambda w=wid: self.open_in_view(w))
        self.add_widget_data(wid, self.row, self.col)
        self.grid_layout.addWidget(wid, self.row, self.col)
        SignalsApp.all.create_path_labels.emit(JsonData.root, len(self.cell_to_wid))

        self.col += 1
        if self.col >= self.col_count:
            self.col = 0
            self.row += 1
 
    def rearrange(self, width: int = None):
        if not self.task_.is_running():
            super().rearrange(width)
    
    def order_(self):
        if not self.task_.is_running():
            super().order_()

    def filter_(self):
        if not self.task_.is_running():
            super().filter_()

    def resize_(self):
        if not self.task_.is_running():
            super().resize_()

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        self.task_.set_should_run(False)