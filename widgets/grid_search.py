import os
from ast import literal_eval
from time import sleep

import sqlalchemy
from numpy import ndarray
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QPixmap
from sqlalchemy.exc import IntegrityError, OperationalError

from cfg import JsonData, Static, ThumbData
from database import CACHE, Dbase, OrderItem
from fit_img import FitImg
from signals import SignalsApp
from utils import URunnable, UThreadPool, Utils

from ._grid import Grid, ThumbSearch
from ._grid_tools import GridTools

SLEEP = 0.2
SEARCH_TEMPLATE = "search_template"
SQL_ERRORS = (IntegrityError, OperationalError)

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
        self.search_text: str = str(search_text)
        self.extensions: tuple = None

    @URunnable.set_running_state
    def run(self):
        try:
            self.setup_text()
            self.scandir_main()

            # if self.should_run:
                # SignalsApp.instance.set_search_title.emit(str(self.search_text))

            # self.signals_.finished_.emit()

        except RuntimeError as e:
            Utils.print_error(parent=None, error=e)

    def setup_text(self):
        extensions = Static.SEARCH_TEMPLATES.get(self.search_text)
        if extensions:
            self.extensions = extensions
            self.process_entry = self.process_extensions
        else:
            self.process_entry = self.process_text

    def process_entry(self, entry: os.DirEntry): ...

    def process_extensions(self, entry: os.DirEntry):
        path = entry.path
        path: str = path.lower()
        if path.endswith(self.extensions):
            return True
        else:
            return False

    def process_text(self, entry: os.DirEntry):
        filename, _ = os.path.splitext(entry.name)
        filename: str = filename.lower()
        search_text: str = self.search_text.lower()
        if filename in search_text or search_text in filename:
            return True
        else:
            return False

    def scandir_main(self):

        stack = [JsonData.root]

        while stack:
            current_dir = stack.pop()

            if not self.should_run:
                return

            with os.scandir(current_dir) as entries:

                for entry in entries:

                    if not self.should_run:
                        return

                    if entry.is_dir():
                        stack.append(entry.path)
                        continue

                    if self.process_entry(entry=entry):
                        self.file_check(entry=entry)
                        

    def file_check(self, entry: os.DirEntry):
        root = os.path.dirname(entry.path)
        db = os.path.join(root, Static.DB_FILENAME)

        dbase = Dbase()
        engine = dbase.create_engine(path=db)
        conn = engine.connect()

        pixmap = self.file_db_check(
            conn=conn,
            entry=entry
        )


    def file_db_check(self, conn: sqlalchemy.Connection, entry: os.DirEntry):
        
        stat = entry.stat()

        order_item = OrderItem(
            src=entry.path,
            size=stat.st_size,
            mod=stat.st_mtime,
            rating=0
        )

        rating, item = GridTools.load_db_item(
            conn=conn,
            order_item=order_item
        )

        print(rating, item)



class GridSearch(Grid):
    def __init__(self, width: int, search_text: str):
        super().__init__(width)

        self.col_count = Utils.get_clmn_count(width)
        self.row, self.col = 0, 0
        self.total = 0

        SignalsApp.instance.bar_bottom_cmd.emit(
            {
                "src": JsonData.root,
                "total": 0
            }
        )

        ThumbSearch.calculate_size()

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

        wid.clicked_.connect(
            lambda w=wid: self.select_one_wid(wid=w)
        )

        wid.control_clicked.connect(
            lambda w=wid: self.control_clicked(wid=w)
        )

        wid.shift_clicked.connect(
            lambda w=wid: self.shift_clicked(wid=w)
        )

        wid.open_in_view.connect(
            lambda w=wid: self.open_in_view(wid=w)
        )

        wid.mouse_moved.connect(
            lambda w=wid: self.drag_event(wid=w)
        )

        self.add_widget_data(
            wid=wid,
            row=self.row,
            col=self.col
        )

        self.grid_layout.addWidget(wid, self.row, self.col)

        self.total += 1
        self.col += 1
        if self.col >= self.col_count:
            self.col = 0
            self.row += 1
 
        # сортируем сетку после каждого 10 виджета
        if self.total % 10 == 0:

            self.order_()

            SignalsApp.instance.bar_bottom_cmd.emit(
                {
                    "total": self.total
                }
            )

    def search_fin(self):

        SignalsApp.instance.bar_bottom_cmd.emit(
            {
                "total": self.total
            }
        )

        self.order_()

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        self.task_.should_run = False