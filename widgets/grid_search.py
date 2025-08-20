import os
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
                             QWidget)

from cfg import Dynamic, Static
from system.items import BaseItem, MainWinItem, SearchItem
from system.tasks import SearchTask
from system.utils import UThreadPool, Utils

from ._base_widgets import MinMaxDisabledWin, USvgSqareWidget, UTextEdit
from .grid import Grid, Thumb


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

        warn = USvgSqareWidget(Static.INTERNAL_ICONS.get("warning.svg"), WinMissedFiles.svg_size)
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

    def __init__(self, main_win_item: MainWinItem):
        super().__init__(main_win_item)
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
        self.is_grid_search = True
        self.total_count_update.emit((len(self.selected_thumbs), 0))
        self.path_bar_update.emit(self.main_win_item.main_dir)
        Thumb.calc_size()

        self.search_task = SearchTask(self.main_win_item, self.search_item)
        self.search_task.sigs.new_widget.connect(self.add_new_widget)
        self.search_task.sigs.finished_.connect(lambda missed_files_list: self.search_fin(missed_files_list))
        UThreadPool.start(self.search_task)

    def add_new_widget(self, base_item: BaseItem):
        thumb = Thumb(base_item.src, base_item.rating)
        thumb.migrate_from_base_item(base_item)
        thumb.set_widget_size()
        thumb.set_no_frame()

        if base_item.get_qimage_storage():
            thumb.set_image(base_item.get_qimage_storage())
        else:
            icon_path = Utils.get_icon_path(base_item.type_, Static.EXTERNAL_ICONS)
            if not os.path.exists(icon_path):
                Utils.create_icon(base_item.type_, icon_path, Static.INTERNAL_ICONS.get("file.svg"))
            thumb.set_svg_icon()

        self.add_widget_data(thumb, self.row, self.col)
        self.grid_layout.addWidget(thumb, self.row, self.col)

        self.total += 1
        self.col += 1
        if self.col >= self.col_count:
            self.col = 0
            self.row += 1
 
        self.total_count_update.emit((len(self.selected_thumbs), self.total))

    def search_fin(self, missed_files_list: list[str]):
        try:
            if not self.cell_to_wid:
                no_images = QLabel(GridSearch.no_result_text)
                no_images.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.grid_layout.addWidget(no_images, 0, 0)

            elif missed_files_list:
                self.win_missed_files = WinMissedFiles(missed_files_list)
                self.win_missed_files.center(self.window())
                self.win_missed_files.show()

            if self.search_task.is_should_run():
                self.finished_.emit()
        except RuntimeError as e:
            Utils.print_error()

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