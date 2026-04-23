import os

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QDragEnterEvent, QDropEvent
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from cfg import Static
from system.items import DataItem, MainWinItem, SearchItem, SortItem
from system.multiprocess import ProcessWorker, SearchTask

from ._base_widgets import (NotifyWid, SmallBtn, USvgSqareWidget, UTextEdit,
                            WinMinCloseOnly)
from .grid import Grid, Thumb
from system.utils import Utils

class DirsWatched:
    def set_should_run(self): ...


class WinMissedFiles(WinMinCloseOnly):
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

        warn = USvgSqareWidget(os.path.join(Static.internal_images_dir, "warning.svg"), WinMissedFiles.svg_size)
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

        ok_btn = SmallBtn(WinMissedFiles.ok_text)
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
    warning_svg = os.path.join(Static.internal_images_dir, "warning.svg")
    pause_time_ms = 1000
    search_timer_ms = 500

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

        def create_thumb(data_item: DataItem):
            thumb = Thumb(data_item)
            thumb.update_all(self.sort_item)
            thumb.set_no_frame()

            if thumb.data_item._img_array is not None:
                thumb.data_item.qimages["src"] = Utils.qimage_from_array(
                    image=data_item._img_array
                )
                for i in Static.image_sizes:
                    thumb.data_item.qimages[i] = Utils.scaled(
                        qimage=thumb.data_item.qimages["src"],
                        size=i
                    )
                thumb.set_image()

            self.add_widget_data(thumb, self.row, self.col)
            self.grid_layout.addWidget(thumb, self.row, self.col)
            self.total += 1
            self.col += 1
            if self.col >= self.col_count:
                self.col = 0
                self.row += 1

        def fin(missed_files: dict[str, str]):
            self.finished_.emit()
            
            if not self.cell_to_wid:
                no_images = QLabel(GridSearch.no_result_text)
                no_images.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.grid_layout.addWidget(no_images, 0, 0)

            if missed_files:
                missed_files = list(missed_files.values())
                self.win_missed_files = WinMissedFiles(missed_files)
                self.win_missed_files.center(self.window())
                self.win_missed_files.show()
        
        def poll_task():
            self.search_timer.stop()
            data_items: list[DataItem] = []
            while not self.search_task.queue.empty():
                result = self.search_task.queue.get()
                if isinstance(result, DataItem):
                    data_items.append(result)
                else:
                    fin(result)
                    break
            if data_items:
                for i in data_items:
                    create_thumb(i)
            selected, total = 0, self.total
            self.total_count_update.emit((selected, total))
            if not self.search_task.is_alive() and self.search_task.queue.empty():
                self.search_task.terminate_join()
            else:
                self.search_timer.start(self.search_timer_ms)


        self.is_grid_search = True
        Thumb.calc_size()
        self.search_item.root_dir = self.main_win_item.abs_current_dir
        self.search_task = ProcessWorker(
            target=SearchTask.start,
            args=(self.search_item, )
        )
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(poll_task)

        self.search_task.start()
        self.search_timer.start(self.search_timer_ms)

    def update_gui(self):
        self.total_count_update.emit((len(self.selected_thumbs), len(self.cell_to_wid)))
        self.path_bar_update.emit(self.main_win_item.abs_current_dir)

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
        if self.search_task and self.search_task.is_alive():
            self.search_task.terminate_join()
        return super().closeEvent(a0)

    def deleteLater(self):
        if self.search_task and self.search_task.is_alive():
            self.search_task.terminate_join()
        return super().deleteLater()
    
    def dragEnterEvent(self, a0: QDragEnterEvent):
        a0.accept()

    def dropEvent(self, a0: QDropEvent):
        noti = NotifyWid(self, self.noti_text, self.warning_svg)
        noti._show()