import os

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QDragEnterEvent, QDropEvent
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from watchdog.events import FileSystemEvent

from cfg import Static
from system.items import (ContextItem, DataItem, MainWinItem, SearchItem,
                          TotalCountItem)
from system.multiprocess import ProcessWorker, SearchTask, WatchdogTask
from system.utils import Utils

from ._base_widgets import (NotifyWid, SmallBtn, UMenu, USvgSqareWidget,
                            UTextEdit, WinMinCloseOnly)
from .actions import ThumbActions
from .grid import Grid, NoItemsLabel, Thumb


class WinMissedFiles(WinMinCloseOnly):
    title_text = "Внимание!"
    descr_text = "Не найдены файлы:"
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
        self.total = 0
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
            selected, total = 0, self.total
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
                QTimer.singleShot(0, self.sort_thumbs)
                QTimer.singleShot(0, self.rearrange_thumbs)
            self.watchdog_timer.start(fast_ms)

        self.watchdog_task = ProcessWorker(
            target=WatchdogTask.start,
            args=(self.main_win_item.abs_current_dir, )
        )
        self.watchdog_timer = QTimer(self)
        self.watchdog_timer.timeout.connect(poll_task)
        self.watchdog_timer.setSingleShot(True)

        self.watchdog_timer.start(fast_ms)
        self.watchdog_task.start()

    def watchdog_apply(self, e: FileSystemEvent):
        print(e.event_type, e.src_path)
        wid: Thumb = self.url_to_wid.get(e.src_path, None)
        if e.event_type == "deleted":
            self.del_thumb(e.src_path)
            # if wid and wid.data_item.is_selected:
                # self.watchdog_modified_files.add(e.src_path)
        # elif e.event_type == "created":
        #     new_thumb = self.new_thumb(e.src_path)            
        #     if e.src_path in self.watchdog_modified_files:
        #         self.select_multiple_thumb(new_thumb)
        #         self.watchdog_modified_files.remove(e.src_path)
        # elif e.event_type == "moved":
        #     self.del_thumb(e.src_path)
        #     new_thumb = self.new_thumb(e.dest_path)
        #     if wid and wid.data_item.is_selected:
        #         self.select_multiple_thumb(new_thumb)
        # modified выпадает только на изменение директории
        # можем игнорировать
        # elif e.event_type == "modified":
            # print(e.src_path)

        if not self.url_to_wid:
            self.no_items_label_remove()
            self.no_items_label_create(NoItemsLabel.no_files)
        else:
            self.no_items_label_remove()

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

    def thumb_actions(self, menu: UMenu, item: ContextItem):
        actions = ThumbActions(menu, item)
        super().base_thumb_actions(menu, item)
        menu.addSeparator()
        menu.add_action(
            action=actions.show_in_folder,
            cmd=lambda: self.go_to_widget.emit(item.urls[-1])
        )

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

    def contextMenuEvent(self, a0):
        super().contextMenuEvent(a0)
        urls: list[str] = []
        data_items: list[DataItem] = []
        for i in self.selected_thumbs:
            urls.append(i.data_item.abs_path)
            data_items.append(i.data_item)
        if not data_items:
            item = DataItem(self.main_win_item.abs_current_dir)
            item.set_properties()
            data_items.append(item)
            urls.append(item.abs_path)
        item = ContextItem(
            main_win_item=self.main_win_item,
            urls=urls,
            data_items=data_items
        )
        menu = UMenu(parent=self)
        if self.wid_under_mouse:
            self.thumb_actions(menu, item)
        else:
            self.base_grid_actions(menu, item)
        menu.show_under_cursor()