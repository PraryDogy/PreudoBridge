import os
from difflib import SequenceMatcher
from time import sleep

from PyQt5.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QCloseEvent
from PyQt5.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
                             QWidget)

from cfg import Dynamic, Static, ThumbData
from fit_img import FitImg
from utils import URunnable, UThreadPool, Utils

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


class SearchFinder(URunnable):
    search_value = 0.70

    def __init__(self, main_dir: str, search_item: SearchItem):
        super().__init__()
        self.signals_ = WorkerSignals()
        self.main_dir = main_dir
        self.search_item = search_item

        self.db_path: str = None
        self.conn = None
        self.pause = False

    @URunnable.set_running_state
    def run(self):
        try:
            self.setup_search()
            self.scandir_recursive()
            self.signals_.finished_.emit()
        except RuntimeError as e:
            Utils.print_error(None, e)

    def compare_words(self, word1: str, word2: str):
        return SequenceMatcher(None, word1, word2).ratio()

    def setup_search(self):

        if self.search_item.get_search_text():
            if self.search_item.get_exactly():
                self.process_entry = self.process_text_exactly
            else:
                self.process_entry = self.process_text_free

        elif self.search_item.get_search_extensions():
            self.process_entry = self.process_extensions

        elif self.search_item.get_search_list():
            if self.search_item.get_exactly():
                self.process_entry = self.proc_list_exactly
            else:
                self.process_entry = self.proc_list_free

    # базовый метод обработки os.DirEntry
    def process_entry(self, entry: os.DirEntry, search_list_lower: list[str]): ...

    def process_extensions(self, entry: os.DirEntry, search_list_lower: list[str]):
        # Поиск файлов с определенным расширением.
        path = entry.path
        path: str = path.lower()
        if path.endswith(self.search_item.get_search_extensions()):
            return True
        else:
            return False

    def process_text_free(self, entry: os.DirEntry, search_list_lower: list[str]):
        # Поиск файлов с именем.
        filename, _ = os.path.splitext(entry.name)
        filename: str = filename.lower()
        search_text: str = self.search_item.get_search_text().lower()

        if self.compare_words(search_text, filename) > SearchFinder.search_value:
            return True
        elif search_text in filename or filename in search_text:
            return True
        else:
            return False
        
    def process_text_exactly(self, entry: os.DirEntry, search_list_lower: list[str]):
        # Поиск файлов с именем.
        filename, _ = os.path.splitext(entry.name)
        filename: str = filename.lower()
        search_text: str = self.search_item.get_search_text().lower()

        if filename == search_text:
            return True
        else:
            return False

    def proc_list_exactly(self, entry: os.DirEntry, search_list_lower: list[str]):
        filename, _ = os.path.splitext(entry.name)
        filename: str = filename.lower()
        for item in search_list_lower:
            if filename == item:
                return True
        return False

    def proc_list_free(self, entry: os.DirEntry, search_list_lower: list[str]):
        filename, _ = os.path.splitext(entry.name)
        filename: str = filename.lower()
        for item in search_list_lower:
            if self.compare_words(item, filename) > SearchFinder.search_value:
                return True
            elif item in filename or filename in item:
                return True
        return False

    def scandir_recursive(self):
        # Инициализируем список с корневым каталогом
        dirs_list = [self.main_dir]
        search_list_lower = [i.lower() for i in self.search_item.get_search_list()]

        while dirs_list:
            # Удаляем последний элемент из списка
            # Функция возвращает удаленный элемент
            current_dir = dirs_list.pop()
            if not self.should_run:
                return
            while self.pause:
                sleep(1)
            try:
                # Сканируем текущий каталог и добавляем новые пути в стек
                self.scan_current_dir(current_dir, dirs_list, search_list_lower)
            except Exception as e:
                continue

    def scan_current_dir(self, dir: str, dirs_list: list, search_list_lower: list[str]):
        # Формируем список имен файлом в нижнем регистре из SEARCH_LIST.
        # Если SEARCH_LIST пуст, значит осуществляется поиск по расширениям
        # или поиск по тексту
        search_list_lower = [i.lower() for i in self.search_item.get_search_list()]

        with os.scandir(dir) as entries:
            for entry in entries:
                if not self.should_run:
                    return
                while self.pause:
                    sleep(1)
                # Если это директория, добавляем ее в dirs_list, чтобы позже
                # обойти эту директорию в scan_current_dir
                if entry.is_dir():
                    dirs_list.append(entry.path)
                    continue
                # Передаем DirEntry и список имен для обработки в process_enry.
                # При этом неважно, пуст список или нет, т.к. при поиске
                # по списку на process_entry назначается функция, которая
                # сможет обработать этот список, в иных случаях на 
                # process_entry назначаются функции, которые проигнорируют
                # этот список читай setup_text.
                if self.process_entry(entry, search_list_lower):
                    self.process_img(entry)

    def process_img(self, entry: os.DirEntry):
        img_array = Utils.read_image(path=entry.path)
        img_array = FitImg.start(
            image=img_array,
            size=ThumbData.DB_IMAGE_SIZE
        )
        pixmap = Utils.pixmap_from_array(image=img_array)
        del img_array

        base_item = BaseItem(entry.path)
        base_item.setup_attrs()
        base_item.set_pixmap_storage(pixmap)

        try:
            self.signals_.new_widget.emit(base_item)
        except Exception as e:
            Utils.print_error(parent=self, error=e)
            self.signals_.new_widget.emit(base_item)
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
        ok_btn.clicked.connect(self.close)
        ok_btn.setFixedWidth(90)
        h_lay.addWidget(ok_btn)

    def keyPressEvent(self, a0):
        if a0.key() == Qt.Key.Key_Escape:
            self.close()
        return super().keyPressEvent(a0)


class GridSearch(Grid):
    def __init__(self, main_dir: str, view_index: int, url_for_select: str):
        super().__init__(main_dir, view_index, url_for_select)
        self.search_item: SearchItem = None
        self.setAcceptDrops(False)

        self.col_count = self.get_col_count()
        self.row, self.col = 0, 0
        self.total = 0

        self.pause_timer = QTimer(self)
        self.pause_timer.timeout.connect(self.remove_pause)
        self.pause_timer.setSingleShot(True)

    def set_search_item(self, search_item: SearchItem):
        self.search_item = search_item

    def start_search(self):
        self.path_bar_update.emit(self.main_dir)
        Thumb.calculate_size()
        self.is_grid_search = True

        print(self.search_item.exactly)

        self.task_ = SearchFinder(self.main_dir, self.search_item)
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

        elif self.search_item.get_search_list():

            done_src = [
                os.path.splitext(i.name)[0]
                for i in self.cell_to_wid.values()
            ]

            missed_files = [
                i
                for i in self.search_item.get_search_list()
                if i not in done_src
            ]

            if missed_files:
                self.win_missed_files = WinMissedFiles(files=missed_files)
                self.win_missed_files.center(self.window())
                self.win_missed_files.show()

            # Dynamic.search_filename_list.clear()

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
        self.task_.pause = False

    def cancel_cmd(self, *args):
        self.task_.should_run = False
        self.search_fin()

    def resizeEvent(self, a0):
        x, y = (a0.size().width() // 2) - 100, 10
        self.resize_()
        return super().resizeEvent(a0)
    
    def closeEvent(self, a0: QCloseEvent | None) -> None:
        self.task_.should_run = False
        self.task_.pause = False