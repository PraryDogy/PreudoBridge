import os
from dataclasses import dataclass
from time import perf_counter

from PyQt5.QtCore import QRect, QSize, Qt, QTimer
from watchdog.events import FileSystemEvent

from cfg import Dynamic, Static
from system.items import (ClipboardItemGlob, DataItem, DirItem, MainWinItem,
                          TotalCountItem)
from system.multiprocess import ImgLoader, ProcessWorker, WatchdogTask
from system.tasks import DirScaner, UThreadPool
from system.utils import Utils

from .grid import Grid, NoItemsLabel, Thumb


@dataclass(slots=True)
class ImgLoaderHelper:
    task: ProcessWorker
    timer: QTimer


class GridStandart(Grid):

    def __init__(self, main_win_item: MainWinItem):
        super().__init__(main_win_item)
        self.setAcceptDrops(True)
        self.watchdog_modified_files = set()
        self.helpers: list[ImgLoaderHelper] = []
        self.scroll_timer = QTimer(self)
        self.scroll_timer.timeout.connect(self.load_visible_thumbs)
        self.scroll_timer.setSingleShot(True)
        self.verticalScrollBar().valueChanged.connect(self.on_scroll)
        self.dir_scaner_start()
        self.watchdog_start()

    def on_scroll(self, scroll_value: int, ms: int = 500):
        self.scroll_timer.stop()
        self.scroll_timer.start(ms)

    def watchdog_start(self, fast_ms=300, slow_ms=1000):

        def poll_task():
            # реже обновлять сетку когда идет процесс копирования
            # иначе слишком часто будут создаваться виджеты с картинками
            # и будет фризиться гуи 
            if ClipboardItemGlob.src_urls:
                ms = slow_ms
            else:
                ms = fast_ms
            self.watchdog_timer.stop()
            events: list[FileSystemEvent] = []
            while not self.watchdog_task.queue.empty():
                events.append(self.watchdog_task.queue.get())
            if events:
                for i in events:
                    self.watchdog_apply(i)
                self.sort_thumbs()
                self.rearrange_thumbs()
            self.watchdog_timer.start(ms)

        self.watchdog_task = ProcessWorker(
            target=WatchdogTask.start,
            args=(self.main_win_item.abs_current_dir, False, )
        )
        self.watchdog_timer = QTimer(self)
        self.watchdog_timer.timeout.connect(poll_task)
        self.watchdog_timer.setSingleShot(True)

        self.watchdog_timer.start(fast_ms)
        self.watchdog_task.start()

    def watchdog_apply(self, e: FileSystemEvent):
        wid: Thumb = self.url_to_wid.get(e.src_path, None)
        if e.event_type == "deleted":
            self.del_thumb(e.src_path)
            if wid and wid.data_item.is_selected:
                self.watchdog_modified_files.add(e.src_path)
        elif e.event_type == "created":
            new_thumb = self.new_thumb(e.src_path)            
            if e.src_path in self.watchdog_modified_files:
                self.select_multiple_thumb(new_thumb)
                self.watchdog_modified_files.remove(e.src_path)
        elif e.event_type == "moved":
            self.del_thumb(e.src_path)
            new_thumb = self.new_thumb(e.dest_path)
            if wid and wid.data_item.is_selected:
                self.select_multiple_thumb(new_thumb)
        if not self.url_to_wid:
            self.no_items_label_remove()
            self.no_items_label_create(NoItemsLabel.no_files)
        else:
            self.no_items_label_remove()

    def load_visible_thumbs(self):
        if not self.grid_wid.isVisible():
            return

        scroll_y = self.verticalScrollBar().value()
        viewport_h = self.viewport().height()
        item_h = Thumb.fixed_height
        spacing = Grid.grid_spacing
        row_h = item_h + spacing
        columns = self.get_max_columns()
        first_row = scroll_y // row_h
        visible_rows = viewport_h // row_h + 1  # запас
        start_index = first_row * columns
        end_index = (first_row + visible_rows) * columns
        thumbs_list = list(self.url_to_wid.values())
        visible_thumbs = thumbs_list[start_index:end_index]
        result = []
        for thumb in visible_thumbs:
            if thumb.data_item.type_ == Static.folder_type:
                continue
            if thumb.data_item.qimages:
                continue
            result.append(thumb)
        if result:
            self.img_loader_start(result)

    def img_loader_start(self, thumbs: list[Thumb], sec = 0.004):

        def process_item(item: DataItem):
            qimages = {"src": Utils.qimage_from_array(item._img_array)}
            for i in Static.image_sizes:
                qimages[i] = Utils.scaled(qimages["src"], i)
            thumb = self.url_to_wid[item.abs_path] # QLabel
            thumb.data_item.qimages.update(qimages)
            thumb.set_image()
            thumb.data_item.qimages_loaded = True

        def poll_task(helper: ImgLoaderHelper):
            helper.timer.stop()
            start = perf_counter()
            while not helper.task.queue.empty():
                process_item(helper.task.queue.get())
                if perf_counter() - start > sec:
                    break
            if not helper.task.is_alive() and helper.task.queue.empty():
                helper.task.terminate_join()
            else:
                helper.timer.start(0)

        self.stop_img_loader_tasks()
        img_task = ProcessWorker(
            target=ImgLoader.start,
            args=([i.data_item for i in thumbs], self.main_win_item, )
        )
        img_timer = QTimer(self)
        helper = ImgLoaderHelper(
            task=img_task,
            timer=img_timer
        )
        img_timer.setSingleShot(True)
        img_timer.timeout.connect(lambda: poll_task(helper))
        self.helpers.append(helper)
        img_task.start()
        img_timer.start(0)
    
    def dir_scaner_start(self):
        dir_item = DirItem(
            data_items=[],
            main_win_item=self.main_win_item
        )
        self.finder_task = DirScaner(dir_item)
        self.finder_task.sigs.finished_.connect(self.dir_scaner_end)
        UThreadPool.start(self.finder_task)

    def dir_scaner_end(self, dir_item: DirItem):
        if len(dir_item.data_items) == 0:
            self.no_items_label_create(NoItemsLabel.no_files)
            return
        item = TotalCountItem(
            selected=len(self.selected_thumbs),
            total=len(dir_item.data_items)
        )
        self.bar_path_update.emit(self.main_win_item.abs_current_dir)
        self.total_count_update.emit(item)
        Thumb.calc_size()
        self.create_thumbs(dir_item.data_items)
        self.select_thumbs()
        # if Dynamic.word_filters:
            # self.filter_thumbs()
        QTimer.singleShot(0, self.rearrange_thumbs)

    def create_thumbs(self, data_items: list[DataItem]):
        for data_item in data_items:
            thumb = Thumb(data_item)
            thumb.update_all(self.main_win_item.sort_item)
            thumb.set_no_frame()
            thumb.set_icon()
            self.add_widget_data(thumb, 0, 0)

    def select_thumbs(self):
        if self.main_win_item.go_to_widget:
            self.main_win_item.urls_to_select.append(
                self.main_win_item.go_to_widget
            )
            self.main_win_item.go_to_widget = ""
        for i in self.main_win_item.urls_to_select:
            if i in self.url_to_wid:
                wid = self.url_to_wid.get(i)
                self.selected_thumbs.append(wid)
                wid.set_frame()

    def new_thumb(self, url: str):
        data = DataItem(url)
        data.set_properties()
        thumb = Thumb(data)
        thumb.update_all(self.main_win_item.sort_item)
        thumb.set_no_frame()
        thumb.set_icon()

        self.add_widget_data(thumb, self.row, self.col)
        self.grid_layout.addWidget(thumb, self.row, self.col)

        self.col += 1
        if self.col >= self.col_count:
            self.col = 0
            self.row += 1

        return thumb

    def rearrange_thumbs(self):
        super().rearrange_thumbs()
        self.load_visible_thumbs()

    def grid_actions(self):
        if ClipboardItemGlob.src_dir:
            self.context_menu.addSeparator()
            self.context_menu.add_action(
                action=self.context_actions.paste_files,
                callback=lambda: self.paste_files.emit()
            )
        self.context_menu.addSeparator()
        self.context_menu.add_action(
            action=self.context_actions.new_folder,
            callback=lambda: self.new_folder.emit()
        )
        self.context_menu.add_action(
            action=self.context_actions.update_grid,
            callback=lambda: self.load_st_grid.emit(self.main_win_item.abs_current_dir)
        )
        self.context_menu.addSeparator()
        super().base_grid_actions()

    def stop_img_loader_tasks(self):
        for i in self.helpers:
            i.timer.stop()
            QTimer.singleShot(0, i.task.terminate_join)
        self.helpers.clear()

    def deleteLater(self):
        self.watchdog_task.terminate_join()
        self.stop_img_loader_tasks()
        return super().deleteLater()
    
    def closeEvent(self, a0):
        self.watchdog_task.terminate_join()
        self.stop_img_loader_tasks()
        return super().closeEvent(a0)

    def dragEnterEvent(self, a0):
        if a0.mimeData().hasUrls():
            a0.acceptProposedAction()
        return super().dragEnterEvent(a0)
    
    def dropEvent(self, a0):
        if not a0.mimeData().urls():
            return
        urls = [
            i.toLocalFile().rstrip(os.sep)
            for i in a0.mimeData().urls()
        ]
        src = os.path.dirname(urls[0])
        if src == self.main_win_item.abs_current_dir:
            print("нельзя копировать в себя через DropEvent")
            return
        else:
            ClipboardItemGlob.src_dir = src
            ClipboardItemGlob.src_urls = urls
            self.paste_files.emit()
        return super().dropEvent(a0)
    
    def contextMenuEvent(self, a0):
        super().contextMenuEvent(a0)
        if self.wid_under_mouse:
            self.base_thumb_actions()
        else:
            self.grid_actions()
        self.context_menu.show_under_mouse()

    def keyPressEvent(self, a0):
        if a0.key() == Qt.Key.Key_V:
            if ClipboardItemGlob.src_urls:
                self.paste_files.emit()
        return super().keyPressEvent(a0)