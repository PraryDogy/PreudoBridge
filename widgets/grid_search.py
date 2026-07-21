import os

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from watchdog.events import FileSystemEvent

from cfg import Static
from system.items import DataItem, MainWinItem, SearchItem, TotalCountItem
from system.multiprocess import ProcessWorker, SearchTask, WatchdogTask
from system.utils import Utils

from ._base_widgets import (NotifyWid, BtnSmall, UMenu, USvgSqareWidget,
                            UTextEdit, UMainWindow)
from .actions import Actions
from .grid import Grid, NoItemsLabel, Thumb


class WinMissedFiles(UMainWindow):
    title_text = "Внимание!"
    descr_text = "Не найдены файлы:"
    ok_text = "Ок"

    def __init__(self, files: list[str]):
        super().__init__()
        self.set_always_on_top()
        self.set_close_only()
        self.setWindowTitle(WinMissedFiles.title_text)

        v_lay = QVBoxLayout(self.centralWidget())
        v_lay.setContentsMargins(10, 5, 10, 5)

        self.first_row_wid = QWidget()
        v_lay.addWidget(self.first_row_wid)
        self.first_row_lay = QHBoxLayout(self.first_row_wid)
        self.first_row_lay.setContentsMargins(0, 0, 0, 0)

        icon = os.path.join(Static.internal_images_dir, "warning.svg")
        warn = USvgSqareWidget(icon, 30)
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
        h_lay = QHBoxLayout(h_wid)
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.setSpacing(10)
        h_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        ok_btn = BtnSmall(WinMissedFiles.ok_text)
        ok_btn.clicked.connect(self.deleteLater)
        ok_btn.setFixedWidth(90)
        h_lay.addWidget(ok_btn)

        self.adjustSize()

    def keyPressEvent(self, a0):
        if a0.key() == Qt.Key.Key_Escape:
            self.deleteLater()
        return super().keyPressEvent(a0)


class GridSearch(Grid):
    search_finished = pyqtSignal()
    no_result_text = "Ничего не найдено"
    noti_text = "Завершите поиск, затем перетащите файлы"
    warning_svg = os.path.join(Static.internal_images_dir, "warning.svg")
    pause_time_ms = 1000
    search_timer_ms = 500

    def __init__(
            self,
            main_win_item: MainWinItem,
            search_item: SearchItem,
            parent: QWidget
    ):

        super().__init__(main_win_item)
        self.setParent(parent)
        self.search_item = search_item
        self.total_widgets = 0
        self.pause_by_btn: bool = False
        self.pause_timer = QTimer(self)
        self.pause_timer.timeout.connect(self.remove_pause)
        self.pause_timer.setSingleShot(True)
        self.start_search()
        self.watchdog_start()

    def start_search(self):

        def create_thumb(data_item: DataItem):
            thumb = Thumb(data_item)
            thumb.update_all(self.main_win_item.sort_item)
            thumb.set_no_frame()

            if thumb.data_item._img_array is not None:
                thumb.data_item.qimages["src"] = Utils.qimage_from_array(
                    image=data_item._img_array
                )
                for i in Static.pixmap_sizes:
                    thumb.data_item.qimages[i] = Utils.scaled(
                        qimage=thumb.data_item.qimages["src"],
                        size=i
                    )
                thumb.set_image()

            current_count = len(self.url_to_wid) 
            cols = self.get_max_columns()
            row, col = divmod(current_count, cols)
            self.add_widget_data(thumb, row, col)
            self.grid_layout.addWidget(thumb, row, col)

        def fin(missed_files: dict[str, str]):
            self.search_finished.emit()
            
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
            selected, total = 0, len(self.url_to_wid)
            item = TotalCountItem(
                selected=selected,
                total=total
            )
            self.total_count_update.emit(item)
            if not self.search_task.is_alive() and self.search_task.queue.empty():
                self.search_task.terminate_join()
            else:
                self.search_timer.start(self.search_timer_ms)


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

    def watchdog_start(self, fast_ms=300, slow_ms=1000):

        def poll_task():
            self.watchdog_timer.stop()
            events: list[FileSystemEvent] = []
            while not self.watchdog_task.queue.empty():
                events.append(self.watchdog_task.queue.get())
            if events:
                for i in events:
                    QTimer.singleShot(0, lambda ev=i: self.watchdog_apply(ev))
                QTimer.singleShot(0, self.sort)
                QTimer.singleShot(0, self.rearrange)
            self.watchdog_timer.start(fast_ms)

        self.watchdog_task = ProcessWorker(
            target=WatchdogTask.start,
            args=(self.main_win_item.abs_current_dir, True, )
        )
        self.watchdog_timer = QTimer(self)
        self.watchdog_timer.timeout.connect(poll_task)
        self.watchdog_timer.setSingleShot(True)

        self.watchdog_timer.start(fast_ms)
        self.watchdog_task.start()

    def watchdog_apply(self, e: FileSystemEvent):
        if e.event_type == "deleted":
            self.del_thumb(e.src_path)

        if not self.url_to_wid:
            self.no_items_label_remove()
            self.no_items_label_create(NoItemsLabel.no_files)
        else:
            self.no_items_label_remove()

    def sort(self):
        self.search_task.pause = True
        super().sort()
        self.rearrange()
        self.pause_timer.stop()
        self.pause_timer.start(GridSearch.pause_time_ms)

    def filter(self):
        self.search_task.pause = True
        super().filter()
        self.rearrange()
        self.pause_timer.stop()
        self.pause_timer.start(GridSearch.pause_time_ms)

    def resize(self):
        self.search_task.pause = True
        super().resize()
        self.rearrange()
        self.pause_timer.stop()
        self.pause_timer.start(GridSearch.pause_time_ms)

    def rearrange(self):
        super().rearrange()

    def remove_pause(self):
        if self.search_task:
            if not self.pause_by_btn:
                self.search_task.pause = False

    def toggle_pause(self, value: bool):
        self.search_task.pause = value
        self.pause_by_btn = value

    def thumb_actions(self):
        url = self.wid_under_mouse.data_item.abs_path
        super().base_thumb_actions()
        self.context_menu.addSeparator()
        self.context_menu.add_action(
            action=self.context_actions.show_in_folder,
            callback=lambda: self.go_to_widget.emit(url)
        )

    def resizeEvent(self, a0):
        self.resize()
        return super().resizeEvent(a0)
    
    def closeEvent(self, a0):   
        self.search_task.terminate_join()
        self.watchdog_task.terminate_join()
        return super().closeEvent(a0)

    def deleteLater(self):
        self.search_task.terminate_join()
        self.watchdog_task.terminate_join()
        return super().deleteLater()
    
    def dragEnterEvent(self, a0: QDragEnterEvent):
        a0.accept()

    def dropEvent(self, a0: QDropEvent):
        noti = NotifyWid(self, self.noti_text, self.warning_svg)
        noti._show()

    def contextMenuEvent(self, a0):
        super().contextMenuEvent(a0)
        if self.wid_under_mouse:
            self.thumb_actions()
        else:
            self.base_grid_actions()
        self.context_menu.show_under_mouse()