import os
from difflib import SequenceMatcher

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QPixmap
from sqlalchemy.exc import IntegrityError, OperationalError

from cfg import JsonData, Static, ThumbData, Dynamic
from database import Dbase, OrderItem
from fit_img import FitImg
from signals import SignalsApp
from utils import URunnable, UThreadPool, Utils

from ._grid import Grid, ThumbSearch
from ._grid_tools import GridTools

SLEEP = 0.2
SQL_ERRORS = (IntegrityError, OperationalError)


class WorkerSignals(QObject):
    new_widget = pyqtSignal(OrderItem)
    finished_ = pyqtSignal()


class SearchFinder(URunnable):
    def __init__(self, search_text: str):
        super().__init__()

        self.signals_ = WorkerSignals()
        self.search_text: str = str(search_text)
        self.extensions: tuple = None

        self.db_path: str = None
        self.conn = None

    @URunnable.set_running_state
    def run(self):
        try:
            self.setup_text()
            self.scandir_main()

            if self.should_run:

                SignalsApp.instance.set_search_title.emit(
                    self.search_text
                )

            self.signals_.finished_.emit()

        except RuntimeError as e:
            Utils.print_error(parent=None, error=e)

    def setup_text(self):
        extensions = Static.SEARCH_TEMPLATES.get(self.search_text)

        if extensions:
            self.extensions = extensions
            self.process_entry = self.process_extensions

        elif self.search_text == Static.SEARCH_LIST_TEXT:
            self.process_entry = self.process_list

        else:
            self.process_entry = self.process_text

    def word_similarity(self, word1: str, word2: str) -> float:
        return SequenceMatcher(None, word1, word2).ratio()

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

        if search_text in filename:
            return True
        else:
            return False
        
    def process_list(self, entry: os.DirEntry):
        filename, _ = os.path.splitext(entry.name)
        filename: str = filename.lower()

        if filename in Dynamic.SEARCH_LIST:
            return True
        else:
            return False

    def scandir_main(self):

        stack = [JsonData.root]

        while stack:
            current_dir = stack.pop()

            if not self.should_run:
                return
            
            try:
                self.scan_current_dir(
                    current_dir=current_dir,
                    stack=stack
                )

            except Exception as e:
                continue

    def scan_current_dir(self, current_dir, stack: list):

        with os.scandir(current_dir) as entries:
            for entry in entries:

                if not self.should_run:
                    return

                if entry.is_dir():
                    stack.append(entry.path)
                    continue

                if self.process_entry(entry=entry):
                    self.process_img(entry=entry)

    def process_img(self, entry: os.DirEntry):
        
        stat = entry.stat()

        img_array = Utils.read_image(path=entry.path)
        img_array = FitImg.start(
            image=img_array,
            size=ThumbData.DB_IMAGE_SIZE
        )

        pixmap = Utils.pixmap_from_array(image=img_array)
        del img_array

        order_item = OrderItem(
            src=entry.path,
            size=stat.st_size,
            mod=stat.st_mtime,
            rating=0
        )

        order_item.pixmap_ = pixmap

        try:
            self.signals_.new_widget.emit(order_item)
        except Exception as e:
            Utils.print_error(parent=self, error=e)
            self.signals_.new_widget.emit(order_item)


class GridSearch(Grid):
    def __init__(self, width: int, search_text: str):
        super().__init__(width)
        self.setAcceptDrops(False)

        self.col_count = Utils.get_clmn_count(width)
        self.row, self.col = 0, 0
        self.total = 0

        SignalsApp.instance.bar_bottom_cmd.emit(
            {"src": JsonData.root, "total": str(self.total)}
        )

        ThumbSearch.calculate_size()

        self.task_ = SearchFinder(search_text)
        self.task_.signals_.new_widget.connect(self.add_new_widget)
        self.task_.signals_.finished_.connect(self.search_fin)
        UThreadPool.start(self.task_)

    def add_new_widget(self, order_item: OrderItem):
        wid = ThumbSearch(
            src=order_item.src,
            size=order_item.size,
            mod=order_item.mod,
            rating=order_item.rating,
            )
        
        if isinstance(order_item.pixmap_, QPixmap):
            wid.set_pixmap(order_item.pixmap_)

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
 
        if self.total % 2 == 0:
            SignalsApp.instance.bar_bottom_cmd.emit(
                {"total": str(self.total)}
            )

    def search_fin(self):
        SignalsApp.instance.bar_bottom_cmd.emit(
            {"total": str(self.total)}
        )

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        self.task_.should_run = False