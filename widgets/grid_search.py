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


class SearchFinder(URunnable):
    sleep_ms = 1000
    new_wid_sleep_ms = 200

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
        if self.search_item.get_files_list():
            for i in self.files_list_lower:
                if i not in self.found_files_list:
                    missed_files_list.append(i)

        try:
            self.signals_.finished_.emit(missed_files_list)
        except RuntimeError as e:
            Utils.print_error(e)

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

        # if self.compare_words(self.text_lower, filename) > SearchFinder.search_value:
            # return True
        if self.text_lower in filename or filename in self.text_lower:
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
                self.found_files_list.append(item)
                return True
        return False

    def process_list_free(self, entry: os.DirEntry):
        filename, _ = self.remove_extension(entry.name)
        filename: str = filename.lower()
        for item in self.files_list_lower:
            if item in filename or filename in item:
                self.found_files_list.append(item)
                return True
        return False

    def scandir_recursive(self):
        # Инициализируем список с корневым каталогом
        dirs_list = [self.main_win_item.main_dir]

        while dirs_list:
            current_dir = dirs_list.pop()

            while self.pause:
                QTest.qSleep(SearchFinder.sleep_ms)
                if not self.is_should_run():
                    return

            if not self.is_should_run():
                return

            try:
                # Сканируем текущий каталог и добавляем новые пути в стек
                self.scan_current_dir(current_dir, dirs_list)
            except RuntimeError as e:
                Utils.print_error(e)
                return
            except Exception as e:
                Utils.print_error(e)
                continue

    def scan_current_dir(self, dir: str, dirs_list: list):
        for entry in os.scandir(dir):
            while self.pause:
                QTest.qSleep(SearchFinder.sleep_ms)
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
        QTest.qSleep(SearchFinder.new_wid_sleep_ms)


class WinMissedFiles(MinMaxDisabledWin):
    title_text = "Внимание!"
    descr_text = "Не найдены файлы:"
    ww, hh = 300, 400
    svg_size = 50
    ok_text = "Ок"

    def __init__(self, files: list[str]):
        super().__init__()
        self.set_modality()
        self.setWindowTitle(WinMissedFiles.title_text)
        self.setMinimumSize(WinMissedFiles.ww, WinMissedFiles.hh)
        self.resize(WinMissedFiles.ww, WinMissedFiles.hh)

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
        self.search_item: SearchItem = None
        self.setAcceptDrops(False)

        # значение общего числа виджетов в сетке для нижнего бара приложения
        self.total = 0
        self.task_: SearchFinder = None
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

        self.task_ = SearchFinder(self.main_win_item, self.search_item)
        self.task_.signals_.new_widget.connect(self.add_new_widget)
        self.task_.signals_.finished_.connect(lambda missed_files_list: self.search_fin(missed_files_list))
        UThreadPool.start(self.task_)

    def add_new_widget(self, base_item: BaseItem):
        self.thumb = Thumb(base_item.src, base_item.rating)
        self.thumb.setParent(self)
        self.thumb.setup_attrs()
        self.thumb.setup_child_widgets()
        self.thumb.set_no_frame()

        generic_icon_path = Utils.get_generic_icon_path(base_item.type_)

        if not generic_icon_path in Dynamic.generic_icon_paths:
            generic_icon_path = Utils.create_generic_icon(base_item.type_)

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

        self.finished_.emit()

    def sort_thumbs(self):
        self.task_.pause = True
        super().sort_thumbs()
        self.rearrange_thumbs()
        self.pause_timer.stop()
        self.pause_timer.start(GridSearch.pause_time_ms)

    def filter_thumbs(self):
        self.task_.pause = True
        super().filter_thumbs()
        self.rearrange_thumbs()
        self.pause_timer.stop()
        self.pause_timer.start(GridSearch.pause_time_ms)

    def resize_thumbs(self):
        self.task_.pause = True
        super().resize_thumbs()
        self.rearrange_thumbs()
        self.pause_timer.stop()
        self.pause_timer.start(GridSearch.pause_time_ms)

    def rearrange_thumbs(self):
        super().rearrange_thumbs()

    def remove_pause(self):
        if self.task_:
            if not self.pause_by_btn:
                self.task_.pause = False

    def toggle_pause(self, value: bool):
        self.task_.pause = value
        self.pause_by_btn = value

    def resizeEvent(self, a0):
        self.resize_thumbs()
        return super().resizeEvent(a0)
    
    def closeEvent(self, a0):
        self.task_.set_should_run(False)
        return super().closeEvent(a0)

    def deleteLater(self):
        self.task_.set_should_run(False)
        return super().deleteLater()