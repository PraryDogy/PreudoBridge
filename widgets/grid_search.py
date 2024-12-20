import os
from ast import literal_eval
from time import sleep

import sqlalchemy
from numpy import ndarray
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QPixmap
from sqlalchemy.exc import IntegrityError, OperationalError

from cfg import JsonData, Static, ThumbData
from database import CACHE, Dbase
from fit_img import FitImg
from signals import SignalsApp
from utils import URunnable, UThreadPool, Utils

from ._grid import Grid, ThumbSearch

SLEEP = 0.2


class WidgetData:
    __slots__ = ["src", "rating", "size", "mod", "pixmap"]

    def __init__(self, src: str, rating: int, size: int, mod: int, pixmap: QPixmap):
        self.src: str = src
        self.rating: int = rating
        self.size: int = size
        self.mod: int = mod
        self.pixmap: QPixmap = pixmap


class WorkerSignals(QObject):
    add_new_widget = pyqtSignal(WidgetData)
    finished_ = pyqtSignal()


class SearchFinder(URunnable):
    def __init__(self, search_text: str):
        super().__init__()

        self.signals_ = WorkerSignals()
        self.search_text: str = search_text
        self.conn: sqlalchemy.Connection = Dbase.engine.connect()

        self.insert_count: int = 0
        self.insert_count_data: list[tuple[sqlalchemy.Insert, str, ndarray]] = []

        ThumbSearch.calculate_size()

    @URunnable.set_running_state
    def run(self):
        try:
            self.setup_text()
            self.walk_dir()

            if self.insert_count > 0:
                self.insert_count_cmd()

            self.conn.close()

            if self.should_run:
                SignalsApp.all_.set_search_title.emit(str(self.search_text))

            self.signals_.finished_.emit()

        except RuntimeError as e:
            Utils.print_error(parent=None, error=e)

    def walk_dir(self):
        stack = [JsonData.root]

        while stack:
            current_dir = stack.pop()

            if not self.should_run:
                return

            try:
                with os.scandir(current_dir) as entries:
                    for entry in entries:
                        if not self.should_run:
                            return

                        if entry.is_dir():
                            stack.append(entry.path)
                            continue

                        if not entry.path.lower().endswith(Static.IMG_EXT):
                            continue

                        if self._should_create_wid(entry):
                            self._process_entry(entry)

            except FileNotFoundError:
                pass
            except Exception:
                pass

    def _should_create_wid(self, entry: os.DirEntry):
        src_lower: str = entry.path.lower()
        if hasattr(self, "is_tuple") and src_lower.endswith(self.search_text):
            return True
        return self.search_text in entry.name

    def _process_entry(self, entry):
        try:
            self.create_wid_cmd(src=entry.path, stat=entry.stat())
            sleep(SLEEP)
        except Exception:
            pass

    def setup_text(self):
        try:
            self.search_text: tuple = literal_eval(self.search_text)
        except (ValueError, SyntaxError):
            pass

        if isinstance(self.search_text, tuple):
            setattr(self, "is_tuple", True)

        elif isinstance(self.search_text, int):
            self.search_text = str(self.search_text)

    def get_stats(self, src: str) -> os.stat_result | None:
        try:
            return os.stat(src)
        except (PermissionError, FileNotFoundError) as e:
            Utils.print_error(self, e)
            return None

    def create_wid_cmd(self, src: str, stat: os.stat_result) -> bool:

        db_data = self.get_db_data(src)

        if db_data is None:
            img_array = Utils.read_image(src)
            small_img_array = FitImg.start(img_array, ThumbData.DB_PIXMAP_SIZE)

            pixmap = Utils.pixmap_from_array(small_img_array)
            rating: int = 0
            new_img = True

        else:
            small_img_array = Utils.read_image_hash(db_data[0])

            pixmap: QPixmap = Utils.pixmap_from_array(small_img_array)
            rating = db_data[2]
            new_img = False

        widget_data = WidgetData(
            src=src,
            rating=rating,
            size=stat.st_size,
            mod=stat.st_mtime,
            pixmap=pixmap
            )

        self.signals_.add_new_widget.emit(widget_data)

        if new_img:
            hash_path = Utils.create_hash_path(src)
        
            if img_array is not None:
                h_, w_ = img_array.shape[:2]
            else:
                h_, w_ = 0, 0
            resol = f"{w_}x{h_}"

            args = [src, hash_path, stat.st_size, stat.st_mtime, resol]
            stmt = self.get_insert_query(*args)

            self.insert_count_data.append((stmt, hash_path, small_img_array))
            self.insert_count += 1

        if self.insert_count == 10:
            self.insert_count_cmd()
            self.insert_count_data.clear()

    def get_db_data(self, src: str) -> list[tuple[str, str, int]] | None:
        try:
            sel_stmt = sqlalchemy.select(
                CACHE.c.hash_path,
                CACHE.c.rating
                ).where(
                    CACHE.c.src == src
                    )
            return self.conn.execute(sel_stmt).first()

        except OperationalError as e:
            Utils.print_error(self, e)
            return None

    def get_insert_query(self, src: str, hash_path: str, size: int, mod: int, resol: str):

        src = os.sep + src.strip().strip(os.sep)
        values_ = Dbase.get_cache_values(src, hash_path, size, mod, resol)

        return sqlalchemy.insert(CACHE).values(**values_)

    def insert_count_cmd(self):
        for stmt, hash_path, small_img_array in self.insert_count_data:

            try:
                self.conn.execute(stmt)

            except IntegrityError as e:
                self.conn.rollback()
                Utils.print_error(parent=self, error=e)
                self.should_run = False
                return None
            
            except OperationalError as e:
                self.conn.rollback()
                Utils.print_error(parent=self, error=e)
                continue

        self.conn.commit()

        # мы пишем раздельно на диск и дб чтобы дб была занята минимальное время
        for stmt, hash_path, small_img_array in self.insert_count_data:
            Utils.write_image_hash(hash_path, small_img_array)

        return True


class GridSearch(Grid):
    def __init__(self, width: int, search_text: str):
        super().__init__(width)

        self.set_main_wid()

        self.col_count = Utils.get_clmn_count(width)
        self.row, self.col = 0, 0
        self.total = 0

        SignalsApp.all_.bar_bottom_cmd.emit(
            {
                "src": JsonData.root,
                "total": 0
            }
        )

        self.task_ = SearchFinder(search_text)
        self.task_.signals_.add_new_widget.connect(self.add_new_widget)
        self.task_.signals_.finished_.connect(self.search_fin)
        UThreadPool.start(self.task_)

    def add_new_widget(self, widget_data: WidgetData):
        wid = ThumbSearch(
            src=widget_data.src,
            size=widget_data.size,
            mod=widget_data.mod,
            rating=widget_data.rating,
            )
        
        if widget_data.pixmap is not None:
            wid.set_pixmap(widget_data.pixmap)

        wid.select.connect(lambda w=wid: self.select_new_widget(w))
        wid.open_in_view.connect(lambda w=wid: self.open_in_view(w))
        wid.find_here.connect(self.open_find_here_win)
        self.add_widget_data(wid, self.row, self.col)
        self.grid_layout.addWidget(wid, self.row, self.col)
        self.total += 1

        self.col += 1
        if self.col >= self.col_count:
            self.col = 0
            self.row += 1
 
        # сортируем сетку после каждого 10 виджета
        if self.total % 10 == 0:

            self.order_()

            SignalsApp.all_.bar_bottom_cmd.emit(
                {
                    "total": self.total
                }
            )

    def search_fin(self):

        SignalsApp.all_.bar_bottom_cmd.emit(
            {
                "total": self.total
            }
        )

        self.order_()

    def rearrange(self, width: int = None):
        super().rearrange(width)
    
    def order_(self):
        super().order_()

    def filter_(self):
        if not self.task_.is_running:
            super().filter_()

    def resize_(self):
        ThumbSearch.calculate_size()
        super().resize_()

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        self.task_.should_run = False