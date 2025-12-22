import os

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QDragEnterEvent, QDropEvent
from PyQt5.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
                             QWidget)

from cfg import Dynamic, Static
from system.items import BaseItem, MainWinItem, SearchItem, SortItem
from system.tasks import SearchTask, UThreadPool
from system.utils import Utils

from ._base_widgets import (MinMaxDisabledWin, NotifyWid, USvgSqareWidget,
                            UTextEdit)
from .grid import Grid, Thumb


class DirsWatched:
    def set_should_run(self): ...


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
        self.centralWidget().setLayout(v_lay)

        self.first_row_wid = QWidget()
        v_lay.addWidget(self.first_row_wid)
        self.first_row_lay = QHBoxLayout()
        self.first_row_lay.setContentsMargins(0, 0, 0, 0)
        self.first_row_wid.setLayout(self.first_row_lay)

        warn = USvgSqareWidget(os.path.join(Static.internal_icons_dir, "warning.svg"), WinMissedFiles.svg_size)
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
    noti_text = "Завершите поиск, затем перетащите файлы"
    warning_svg = os.path.join(Static.internal_icons_dir, "warning.svg")
    pause_time_ms = 700

    def __init__(
            self,
            main_win_item: MainWinItem,
            sort_item: SortItem,
            search_item: SearchItem,
            parent: QWidget,
            is_grid_search: bool
    ):

        super().__init__(main_win_item, is_grid_search)
        self.setParent(parent)

        self.search_item = search_item
        self.sort_item = sort_item

        self.total = 0
        self.pause_by_btn: bool = False

        self.pause_timer = QTimer(self)
        self.pause_timer.timeout.connect(self.remove_pause)
        self.pause_timer.setSingleShot(True)

        self.start_search()

    def start_search(self):

        def new_search_thumb(base_item: BaseItem):
            thumb = Thumb(base_item.src, base_item.rating)
            thumb.migrate_from_base_item(base_item)
            thumb.set_widget_size()
            thumb.set_no_frame()
            if thumb.qimages:
                thumb.set_image()
            else:
                thumb.set_uti_image()
            self.add_widget_data(thumb, self.row, self.col)
            self.grid_layout.addWidget(thumb, self.row, self.col)
            self.total += 1
            self.col += 1
            if self.col >= self.col_count:
                self.col = 0
                self.row += 1
            
            QTimer.singleShot(100, lambda: self.total_count_update.emit((len(self.selected_thumbs), len(self.cell_to_wid))))

        def fin(missed_files_list: list[str]):
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

        QTimer.singleShot(100, lambda: self.total_count_update.emit((len(self.selected_thumbs), len(self.cell_to_wid))))
        QTimer.singleShot(100, lambda: self.path_bar_update.emit(self.main_win_item.main_dir))
        self.is_grid_search = True
        Thumb.calc_size()
        self.search_task = SearchTask(self.main_win_item, self.search_item)
        self.search_task.sigs.new_widget.connect(new_search_thumb)
        self.search_task.sigs.finished_.connect(lambda lst: fin(lst))
        UThreadPool.start(self.search_task)

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
        for i in self.cell_to_wid.values():
            i.setParent(None)
            i.deleteLater()
        return super().closeEvent(a0)

    def deleteLater(self):
        self.search_task.set_should_run(False)
        for i in self.cell_to_wid.values():
            i.setParent(None)
            i.deleteLater()
        return super().deleteLater()
    
    def dragEnterEvent(self, a0: QDragEnterEvent):
        a0.accept()

    def dropEvent(self, a0: QDropEvent):
        noti = NotifyWid(self, self.noti_text, self.warning_svg)
        noti._show()