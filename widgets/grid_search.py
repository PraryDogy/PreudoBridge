import os
import weakref
from difflib import SequenceMatcher
from time import sleep

from PyQt5.QtCore import QObject, QRunnable, Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
                             QWidget)

from cfg import Dynamic, Static, ThumbData
from fit_img import FitImg
from utils import UThreadPool, Utils

from ._base_items import (BaseItem, MinMaxDisabledWin, SearchItem,
                          USvgSqareWidget, UTextEdit)
from .grid import Grid, Thumb

ATTENTION_T = "Внимание!"
MISSED_FILES = "Не найдены файлы:"
SELECT_ALL_T = "Выделить все"
NO_RESULT = "Ничего не найдено"
SEARCHING = "Идет поиск"
STOP = "Стоп"
RESIZE_TIMER_COUNT = 700

class WorkerSignals(QObject):
    new_widget = pyqtSignal(BaseItem)
    finished_ = pyqtSignal()


class SearchFinder(QRunnable):
    search_value = 0.85

    def __init__(self, main_dir: str, search_item: SearchItem, parent: QWidget):
        super().__init__()
        self.signals_ = WorkerSignals()
        self.main_dir = main_dir
        self.parent_ref = weakref.ref(parent)

        self.search_item = search_item
        self.files_list_lower: list[str] = []
        self.text_lower: str = None
        self.exts_lower: tuple[str] = None

        self.db_path: str = None
        self.conn = None
        self.pause = False

    def run(self):
        try:
            self.setup_search()
            self.scandir_recursive()
            if self.parent_ref():
                self.signals_.finished_.emit()
        except RuntimeError as e:
            Utils.print_error(None, e)

    def setup_search(self):
        if self.search_item.get_files_list():
            if self.search_item.get_exactly():
                self.process_entry = self.process_list_exactly
            else:
                self.process_entry = self.process_list_free
            for i in self.search_item.get_files_list():
                filename, _ = self.remove_extension(i)
                self.files_list_lower.append(filename.lower())

        elif self.search_item.get_extensions():
            self.process_entry = self.process_extensions
            exts_lower = (i.lower() for i in self.search_item.get_extensions())
            self.exts_lower = tuple(exts_lower)

        # последним мы проверяем search item search text, так как search text
        # есть и при поиске по шаблонам и при поиске по списку
        elif self.search_item.get_text():
            if self.search_item.get_exactly():
                self.process_entry = self.process_text_exactly
            else:
                self.process_entry = self.process_text_free
            self.text_lower = self.search_item.get_text().lower()

    def compare_words(self, word1: str, word2: str):
        return SequenceMatcher(None, word1, word2).ratio()
    
    def remove_extension(self, filename: str):
        return os.path.splitext(filename)
        
    # базовый метод обработки os.DirEntry
    def process_entry(self, entry: os.DirEntry): ...

    def process_extensions(self, entry: os.DirEntry):
        # Поиск файлов с определенным расширением.
        path = entry.path
        path: str = path.lower()
        if path.endswith(self.exts_lower):
            return True
        else:
            return False

    def process_text_free(self, entry: os.DirEntry):
        # Поиск файлов с именем.
        filename, _ = self.remove_extension(entry.name)
        filename: str = filename.lower()

        if self.compare_words(self.text_lower, filename) > SearchFinder.search_value:
            return True
        elif self.text_lower in filename or filename in self.text_lower:
            return True
        else:
            return False
        
    def process_text_exactly(self, entry: os.DirEntry):
        # Поиск файлов с именем.
        filename, _ = self.remove_extension(entry.name)
        filename: str = filename.lower()

        if filename == self.text_lower:
            return True
        else:
            return False

    def process_list_exactly(self, entry: os.DirEntry):
        filename, _ = self.remove_extension(entry.name)
        filename: str = filename.lower()
        for item in self.files_list_lower:
            if filename == item:
                return True
        return False

    def process_list_free(self, entry: os.DirEntry):
        filename, _ = self.remove_extension(entry.name)
        filename: str = filename.lower()
        for item in self.files_list_lower:
            if self.compare_words(item, filename) > SearchFinder.search_value:
                return True
            elif item in filename or filename in item:
                return True
        return False

    def scandir_recursive(self):
        # Инициализируем список с корневым каталогом
        dirs_list = [self.main_dir]

        while dirs_list:
            # Удаляем последний элемент из списка
            # Функция возвращает удаленный элемент
            current_dir = dirs_list.pop()
            if not self.parent_ref():
                return
            while self.pause:
                sleep(1)
            try:
                # Сканируем текущий каталог и добавляем новые пути в стек
                self.scan_current_dir(current_dir, dirs_list)
            except Exception as e:
                print(e)
                continue

    def scan_current_dir(self, dir: str, dirs_list: list):
        for entry in os.scandir(dir):
            if not self.parent_ref():
                return
            while self.pause:
                sleep(1)
            if entry.name.startswith("."):
                continue
            if entry.is_dir():
                dirs_list.append(entry.path)
                continue
            if self.process_entry(entry):
                self.process_img(entry)

    def process_img(self, entry: os.DirEntry):
        img_array = Utils.read_image(entry.path)
        img_array = FitImg.start(img_array, ThumbData.DB_IMAGE_SIZE)
        pixmap = Utils.pixmap_from_array(img_array)
        del img_array

        base_item = BaseItem(entry.path)
        base_item.setup_attrs()
        base_item.set_pixmap_storage(pixmap)

        try:
            self.signals_.new_widget.emit(base_item)
        except Exception as e:
            # почему то даже когда parent_ref = None, 
            # поиск продолжает выполняться, а так мы отлавливаем, что parent
            # был уничтожен и выходим из потока
            # предотвращаем segmentation fault
            Utils.print_error(self, e)
            quit()
        sleep(0.1)


class WinMissedFiles(MinMaxDisabledWin):
    def __init__(self, files: list[str]):
        super().__init__()
        self.setWindowTitle(ATTENTION_T)
        self.setMinimumSize(300, 300)
        self.resize(300, 400)

        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(10, 5, 10, 5)
        self.setLayout(v_lay)

        first_row_wid = QWidget()
        v_lay.addWidget(first_row_wid)
        first_row_lay = QHBoxLayout()
        first_row_lay.setContentsMargins(0, 0, 0, 0)
        first_row_wid.setLayout(first_row_lay)

        warn = USvgSqareWidget(Static.WARNING_SVG, 50)
        first_row_lay.addWidget(warn)

        label_ = QLabel(text=MISSED_FILES)
        first_row_lay.addWidget(label_)

        scrollable = UTextEdit()
        scrollable.setText("\n".join(files))
        scrollable.setReadOnly(True)
        scrollable.setCursor(Qt.CursorShape.IBeamCursor)
        v_lay.addWidget(scrollable)

        h_wid = QWidget()
        v_lay.addWidget(h_wid)
        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.setSpacing(10)
        h_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h_wid.setLayout(h_lay)

        ok_btn = QPushButton(text="Ок")
        ok_btn.clicked.connect(self.deleteLater)
        ok_btn.setFixedWidth(90)
        h_lay.addWidget(ok_btn)

    def keyPressEvent(self, a0):
        if a0.key() == Qt.Key.Key_Escape:
            self.deleteLater()
        return super().keyPressEvent(a0)


class GridSearch(Grid):
    finished_ = pyqtSignal()

    def __init__(self, main_dir: str, view_index: int, url_for_select: str):
        super().__init__(main_dir, view_index, url_for_select)
        self.search_item: SearchItem = None
        self.setAcceptDrops(False)

        self.total = 0
        self.task_: SearchFinder = None

        self.pause_timer = QTimer(self)
        self.pause_timer.timeout.connect(self.remove_pause)
        self.pause_timer.setSingleShot(True)

    def set_search_item(self, search_item: SearchItem):
        self.search_item = search_item

    def start_search(self):
        # обязательно делать именно после инициации, так как только тогда
        # get_col_count найдет родительское окно GridSearch
        self.col_count = self.get_col_count()

        self.sort_bar_update.emit(0)
        self.path_bar_update.emit(self.main_dir)
        Thumb.calculate_size()
        self.is_grid_search = True

        self.task_ = SearchFinder(self.main_dir, self.search_item, self)
        self.task_.signals_.new_widget.connect(self.add_new_widget)
        self.task_.signals_.finished_.connect(self.search_fin)
        UThreadPool.start(self.task_)

    def add_new_widget(self, base_item: BaseItem):
        thumb = Thumb(base_item.src, base_item.rating)
        thumb.setup_attrs()
        thumb.setup_child_widgets()
        thumb.set_no_frame()

        generic_icon_path = Utils.get_generic_icon_path(base_item.type_)

        if not generic_icon_path in Dynamic.generic_icon_paths:
            generic_icon_path = Utils.create_generic_icon(base_item.type_)

        if base_item.src.count(os.sep) == 2:
            thumb.set_svg_icon(Static.HDD_SVG)

        else:
            thumb.set_svg_icon(generic_icon_path)
        
        if base_item.get_pixmap_storage():
            thumb.set_pixmap_storage(base_item.get_pixmap_storage())
            thumb.set_image(base_item.get_pixmap_storage())

        self.add_widget_data(thumb, self.row, self.col)
        self.grid_layout.addWidget(thumb, self.row, self.col)

        self.total += 1
        self.col += 1
        if self.col >= self.col_count:
            self.col = 0
            self.row += 1
 
        self.sort_bar_update.emit(self.total)

    def search_fin(self):
        if not self.cell_to_wid:
            no_images = QLabel(text=NO_RESULT)
            no_images.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.addWidget(no_images, 0, 0)

        elif self.search_item.get_files_list():

            done_src = [i.name for i in self.cell_to_wid.values()]

            missed_files = [
                i
                for i in self.search_item.get_files_list()
                if i not in done_src
            ]

            if missed_files:
                self.win_missed_files = WinMissedFiles(files=missed_files)
                self.win_missed_files.center(self.window())
                self.win_missed_files.show()

        self.finished_.emit()

    def sort_(self):
        self.task_.pause = True
        self.col_count = self.get_col_count()
        super().sort_()
        self.rearrange()
        self.pause_timer.stop()
        self.pause_timer.start(RESIZE_TIMER_COUNT)

    def filter_(self):
        self.task_.pause = True
        super().filter_()
        self.rearrange()
        self.pause_timer.stop()
        self.pause_timer.start(RESIZE_TIMER_COUNT)

    def resize_(self):
        self.task_.pause = True
        super().resize_()
        self.rearrange()
        self.pause_timer.stop()
        self.pause_timer.start(RESIZE_TIMER_COUNT)

    def rearrange(self):
        # нам нужно вычислить новое количество колонок, актуальную строку
        # и столбец для вставки нового виджета
        self.col_count = self.get_col_count()
        self.row = len(self.cell_to_wid) // self.col_count
        self.col = len(self.cell_to_wid) % self.col_count
        super().rearrange()

    def remove_pause(self):
        if self.task_:
            self.task_.pause = False

    def resizeEvent(self, a0):
        self.resize_()
        return super().resizeEvent(a0)
    