import difflib
import os
import weakref
from difflib import SequenceMatcher

from PyQt5.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
                             QWidget)

from cfg import Dynamic, Static, ThumbData
from utils import FitImg, Utils

from ._base_items import (BaseItem, MainWinItem, MinMaxDisabledWin, SearchItem,
                          URunnable, USvgSqareWidget, UTextEdit, UThreadPool)
from .grid import Grid, Thumb


class WorkerSignals(QObject):
    new_widget = pyqtSignal(BaseItem)
    finished_ = pyqtSignal(list)


class SearchTask(URunnable):
    sleep_ms = 1000
    new_wid_sleep_ms = 200
    ratio = 0.85

    def __init__(self, main_win_item: MainWinItem, search_item: SearchItem):
        super().__init__()
        self.signals_ = WorkerSignals()
        self.main_win_item = main_win_item
        self.found_files_list: list[str] = []

        self.search_item = search_item
        self.files_list_lower: list[str] = []
        self.text_lower: str = None
        self.exts_lower: tuple[str] = None

        self.db_path: str = None
        self.conn = None
        self.pause = False

    def task(self):
        self.setup_search()
        self.scandir_recursive()
        
        missed_files_list: list[str] = []

        if isinstance(self.search_item.get_content(), list):
            if self.is_should_run():

                no_ext_list = [
                    os.path.splitext(i)[0]
                    for i in self.search_item.get_content()
                ]

                for i in no_ext_list:
                    if i not in self.found_files_list:
                        missed_files_list.append(i)

        try:
            self.signals_.finished_.emit(missed_files_list)
        except RuntimeError as e:
            Utils.print_error(e)

    def setup_search(self):
        if isinstance(self.search_item.get_content(), list):
            if self.search_item.get_filter() == 0:
                self.process_entry = self.process_list_free
            elif self.search_item.get_filter() == 1:
                self.process_entry = self.process_list_exactly
            else:
                self.process_entry = self.process_list_contains

            for i in self.search_item.get_content():
                filename, _ = self.remove_extension(i)
                self.files_list_lower.append(filename.lower())

        elif isinstance(self.search_item.get_content(), tuple):
            self.process_entry = self.process_extensions
            exts_lower = (i.lower() for i in self.search_item.get_content())
            self.exts_lower = tuple(exts_lower)

        elif isinstance(self.search_item.get_content(), str):
            if self.search_item.get_filter() == 0:
                self.process_entry = self.process_text_free
            elif self.search_item.get_filter() == 1:
                self.process_entry = self.process_text_exactly
            else:
                self.process_entry = self.process_text_contains

            self.text_lower = self.search_item.get_content().lower()
    
    def remove_extension(self, filename: str):
        return os.path.splitext(filename)
        
    # базовый метод обработки os.DirEntry
    def process_entry(self, entry: os.DirEntry): ...

    def process_extensions(self, entry: os.DirEntry):
        path = entry.path
        path: str = path.lower()
        if path.endswith(self.exts_lower):
            return True
        else:
            return False

    def process_text_free(self, entry: os.DirEntry):
        filename, _ = self.remove_extension(entry.name)
        filename: str = filename.lower()
        if self.similarity_ratio(self.text_lower, filename) > SearchTask.ratio:
            return True
        else:
            return False
        
    def process_text_exactly(self, entry: os.DirEntry):
        filename, _ = self.remove_extension(entry.name)
        filename: str = filename.lower()
        if filename == self.text_lower:
            return True
        else:
            return False

    def process_text_contains(self, entry: os.DirEntry):
        filename, _ = self.remove_extension(entry.name)
        filename: str = filename.lower()
        if self.text_lower in filename or filename in self.text_lower:
            return True
        else:
            return False

    def process_list_exactly(self, entry: os.DirEntry):
        true_filename, _ = self.remove_extension(entry.name)
        filename: str = true_filename.lower()
        for item in self.files_list_lower:
            if filename == item:
                self.found_files_list.append(true_filename)
                return True
        return False

    def process_list_free(self, entry: os.DirEntry):
        true_filename, _ = self.remove_extension(entry.name)
        filename: str = true_filename.lower()
        for item in self.files_list_lower:
            if self.similarity_ratio(item, filename) > SearchTask.ratio:
                self.found_files_list.append(true_filename)
                return True
        return False

    def process_list_contains(self, entry: os.DirEntry):
        true_filename, _ = self.remove_extension(entry.name)
        filename: str = true_filename.lower()
        for item in self.files_list_lower:
            if item in filename or filename in item:
                self.found_files_list.append(true_filename)
                return True
        return False

    def similarity_ratio(self, a: str, b: str) -> float:
        return difflib.SequenceMatcher(None, a, b).ratio()

    def scandir_recursive(self):
        # Инициализируем список с корневым каталогом
        dirs_list = [self.main_win_item.main_dir]

        while dirs_list:
            current_dir = dirs_list.pop()

            while self.pause:
                QTest.qSleep(SearchTask.sleep_ms)
                if not self.is_should_run():
                    return

            if not self.is_should_run():
                return

            if not os.path.exists(current_dir):
                continue

            try:
                # Сканируем текущий каталог и добавляем новые пути в стек
                self.scan_current_dir(current_dir, dirs_list)
            except OSError as e:
                Utils.print_error(e)
                continue
            except Exception as e:
                Utils.print_error(e)
                continue
            except RuntimeError as e:
                Utils.print_error(e)
                return

    def scan_current_dir(self, dir: str, dirs_list: list):
        for entry in os.scandir(dir):
            while self.pause:
                QTest.qSleep(SearchTask.sleep_ms)
                if not self.is_should_run():
                    return
            if not self.is_should_run():
                return
            if entry.name.startswith(Static.hidden_file_syms):
                continue
            if entry.is_dir():
                dirs_list.append(entry.path)
                continue
            if self.process_entry(entry):
                self.process_img(entry)

    def process_img(self, entry: os.DirEntry):
        self.img_array = Utils.read_image(entry.path)
        self.img_array = FitImg.start(self.img_array, ThumbData.DB_IMAGE_SIZE)
        self.pixmap = Utils.pixmap_from_array(self.img_array)
        self.base_item = BaseItem(entry.path)
        self.base_item.setup_attrs()
        self.base_item.set_pixmap_storage(self.pixmap)
        self.signals_.new_widget.emit(self.base_item)
        QTest.qSleep(SearchTask.new_wid_sleep_ms)


class WinMissedFiles(MinMaxDisabledWin):
    title_text = "Внимание!"
    descr_text = "Не найдены файлы:"
    svg_size = 50
    ok_text = "Ок"

    def __init__(self, files: list[str]):
        super().__init__()
        self.set_modality()
        self.setWindowTitle(WinMissedFiles.title_text)

        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(10, 5, 10, 5)
        self.setLayout(v_lay)

        self.first_row_wid = QWidget()
        v_lay.addWidget(self.first_row_wid)
        self.first_row_lay = QHBoxLayout()
        self.first_row_lay.setContentsMargins(0, 0, 0, 0)
        self.first_row_wid.setLayout(self.first_row_lay)

        warn = USvgSqareWidget(Static.WARNING_SVG, WinMissedFiles.svg_size)
        self.first_row_lay.addWidget(warn)

        label_ = QLabel(WinMissedFiles.descr_text)
        self.first_row_lay.addWidget(label_)

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

        ok_btn = QPushButton(WinMissedFiles.ok_text)
        ok_btn.clicked.connect(self.deleteLater)
        ok_btn.setFixedWidth(90)
        h_lay.addWidget(ok_btn)

        self.adjustSize()

    def keyPressEvent(self, a0):
        if a0.key() == Qt.Key.Key_Escape:
            self.deleteLater()
        return super().keyPressEvent(a0)


class GridSearch(Grid):
    finished_ = pyqtSignal()
    no_result_text = "Ничего не найдено"
    pause_time_ms = 700

    def __init__(self, main_win_item: MainWinItem, view_index: int):
        super().__init__(main_win_item, view_index)
        self.setAcceptDrops(False)
        self.search_item: SearchItem = None

        # значение общего числа виджетов в сетке для нижнего бара приложения
        self.total = 0
        self.pause_by_btn: bool = False

        self.pause_timer = QTimer(self)
        self.pause_timer.timeout.connect(self.remove_pause)
        self.pause_timer.setSingleShot(True)

    def set_search_item(self, search_item: SearchItem):
        """
        Устанавливает search_item
        Существует только для того, чтобы не передавать через аргумент в инициаторе
        """
        self.search_item = search_item

    def start_search(self):
        self.total_count_update.emit(0)
        self.path_bar_update.emit(self.main_win_item.main_dir)
        Thumb.calculate_size()
        self.is_grid_search = True

        self.search_task = SearchTask(self.main_win_item, self.search_item)
        self.search_task.signals_.new_widget.connect(self.add_new_widget)
        self.search_task.signals_.finished_.connect(lambda missed_files_list: self.search_fin(missed_files_list))
        UThreadPool.start(self.search_task)

    def add_new_widget(self, base_item: BaseItem):
        self.thumb = Thumb(base_item.src, base_item.rating)
        self.thumb.setParent(self)
        self.thumb.setup_attrs()
        self.thumb.setup_child_widgets()
        self.thumb.set_no_frame()

        icon_path = Utils.get_generic_icon_path(base_item.type_, Static.GENERIC_ICONS_DIR)
        if icon_path not in Dynamic.generic_icon_paths:
            Utils.create_generic_icon(base_item.type_, icon_path, Static.FILE_SVG)

        self.thumb.set_svg_icon()
        
        if base_item.get_pixmap_storage():
            self.thumb.set_pixmap_storage(base_item.get_pixmap_storage())
            self.thumb.set_image(base_item.get_pixmap_storage())

        self.add_widget_data(self.thumb, self.row, self.col)
        self.grid_layout.addWidget(self.thumb, self.row, self.col)

        self.total += 1
        self.col += 1
        if self.col >= self.col_count:
            self.col = 0
            self.row += 1
 
        self.total_count_update.emit(self.total)

    def search_fin(self, missed_files_list: list[str]):
        if not self.cell_to_wid:
            no_images = QLabel(GridSearch.no_result_text)
            no_images.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.addWidget(no_images, 0, 0)

        elif missed_files_list:
            self.win_missed_files = WinMissedFiles(missed_files_list)
            self.win_missed_files.center(self.window())
            self.win_missed_files.show()

        try:
            if self.search_task.is_should_run():
                self.finished_.emit()
        except RuntimeError as e:
            Utils.print_error(e)

    def sort_thumbs(self):
        self.search_task.pause = True
        super().sort_thumbs()
        self.rearrange_thumbs()
        self.pause_timer.stop()
        self.pause_timer.start(GridSearch.pause_time_ms)

    def filter_thumbs(self):
        self.search_task.pause = True
        super().filter_thumbs()
        self.rearrange_thumbs()
        self.pause_timer.stop()
        self.pause_timer.start(GridSearch.pause_time_ms)

    def resize_thumbs(self):
        self.search_task.pause = True
        super().resize_thumbs()
        self.rearrange_thumbs()
        self.pause_timer.stop()
        self.pause_timer.start(GridSearch.pause_time_ms)

    def rearrange_thumbs(self):
        super().rearrange_thumbs()

    def remove_pause(self):
        if self.search_task:
            if not self.pause_by_btn:
                self.search_task.pause = False

    def toggle_pause(self, value: bool):
        self.search_task.pause = value
        self.pause_by_btn = value

    def resizeEvent(self, a0):
        self.resize_thumbs()
        return super().resizeEvent(a0)
    
    def closeEvent(self, a0):
        self.search_task.set_should_run(False)
        return super().closeEvent(a0)

    def deleteLater(self):
        self.search_task.set_should_run(False)
        return super().deleteLater()