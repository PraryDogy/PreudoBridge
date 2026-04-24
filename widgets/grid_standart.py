import os
from time import perf_counter

from PyQt5.QtCore import QRect, QSize, QTimer
from watchdog.events import FileSystemEvent

from cfg import Dynamic, JsonData, Static
from system.items import (ClipboardItemGlob, ContextItem, DataItem, DirItem,
                          MainWinItem, TotalCountItem)
from system.multiprocess import (ImgLoader, ImgLoaderHelper, ProcessWorker,
                                 WatchdogTask)
from system.tasks import DirScaner, UThreadPool
from system.utils import Utils

from ._base_widgets import UMenu
from .grid import Grid, NoItemsLabel, Thumb
from .win_rename import WinRename


class GridStandart(Grid):

    def __init__(self, main_win_item: MainWinItem, is_grid_search: bool):
        super().__init__(main_win_item, is_grid_search)
        self.setAcceptDrops(True)
        self.watchdog_modified_files = set()
        self.helpers: list[ImgLoaderHelper] = []
        self.scroll_timer = QTimer(self)
        self.scroll_timer.timeout.connect(self.load_visible_thumbs_images)
        self.scroll_timer.setSingleShot(True)
        self.verticalScrollBar().valueChanged.connect(self.on_scroll)
        self.watchdog_start()

    def on_scroll(self, ms: int = 500):
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
                    QTimer.singleShot(0, lambda ev=i: self.watchdog_apply(ev))
                QTimer.singleShot(0, self.sort_thumbs)
                QTimer.singleShot(0, self.rearrange_thumbs)
            self.watchdog_timer.start(ms)

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
        # modified выпадает только на изменение директории
        # можем игнорировать
        # elif e.event_type == "modified":
            # print(e.src_path)

        if not self.url_to_wid:
            self.no_items_label_remove()
            self.no_items_label_create(NoItemsLabel.no_files)
        else:
            self.no_items_label_remove()

    def load_visible_thumbs_images(self):
        if not self.grid_wid.isVisible():
            return

        thumbs: list[Thumb] = []
        self.grid_wid.layout().activate() 
        visible_rect = self.viewport().rect()  # область видимой части
        for thumb in self.url_to_wid.values():
            stmt = (
                # если у виджета уже есть изображения
                thumb.data_item.qimages,
                # если виджет это папка
                thumb.data_item.type_ == Static.folder_type,
                # если виджет в загруженных
                thumb in self.loaded_thumbs
            )
            if any(stmt):
                continue
            widget_rect = self.viewport().mapFromGlobal(
                thumb.mapToGlobal(thumb.rect().topLeft())
            )
            qsize = QSize(thumb.width(), thumb.height())
            widget_rect = QRect(widget_rect, qsize)
            if visible_rect.intersects(widget_rect):
                thumbs.append(thumb)

        if thumbs:
            self.loaded_thumbs.extend(thumbs)
            self.img_loader_start(thumbs)

    def img_loader_start(self, thumbs: list[Thumb], sec = 0.004):

        def process_item(item: DataItem):
            qimages = {"src": Utils.qimage_from_array(item._img_array)}
            for i in Static.image_sizes:
                qimages[i] = Utils.scaled(qimages["src"], i)
            thumb = self.url_to_wid[item.abs_path] # QLabel
            thumb.data_item.qimages.update(qimages)
            thumb.set_image()

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
        self.ignore_mouse = True
        dir_item = DirItem(
            data_items=[],
            main_win_item=self.main_win_item,
            sort_item=self.sort_item
        )
        self.finder_task = DirScaner(dir_item)
        self.finder_task.sigs.finished_.connect(self.dir_scaner_end)
        UThreadPool.start(self.finder_task)

    def dir_scaner_end(self, dir_item: DirItem):
        if len(dir_item.data_items) == 0:
            self.no_items_label_create(NoItemsLabel.no_files)
            self.load_finished.emit()
            return
        Thumb.calc_size()

        self.bar_path_update.emit(self.main_win_item.abs_current_dir)
        item = TotalCountItem(
            selected=len(self.selected_thumbs),
            total=len(dir_item.data_items)
        )
        self.total_count_update.emit(item)
        self.create_thumbs_start(dir_item.data_items)

    def create_thumbs_start(self, data_items: list[DataItem]):
        def add_one_thumb():
            if self._thumb_index >= len(self.data_items):
                self.data_items = None
                self._thumb_index = 0
                self.create_thumbs_end()
                return
            data_item = self.data_items[self._thumb_index]
            thumb = Thumb(data_item)
            thumb.update_all(self.sort_item)
            thumb.set_no_frame()
            thumb.set_icon()
            self.add_widget_data(thumb, self.row, self.col)
            self.grid_layout.addWidget(thumb, self.row, self.col)
            self.col += 1
            if self.col >= self.col_count:
                self.col = 0
                self.row += 1
            self._thumb_index += 1
            QTimer.singleShot(0, add_one_thumb)

        self.col_count = self.get_clmn_count()
        self._thumb_index = 0
        self.data_items = data_items
        self.row = 0
        self.col = 0
        add_one_thumb()

    def create_thumbs_end(self):
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
        if Dynamic.word_filters:
            self.filter_thumbs()
        # почему то без таймера срабатывает через раз
        QTimer.singleShot(0, self.rearrange_thumbs)
        self.load_finished.emit()
        self.ignore_mouse = False

    def new_thumb(self, url: str):
        data = DataItem(url)
        data.set_properties()
        thumb = Thumb(data)
        thumb.update_all(self.sort_item)
        thumb.set_no_frame()
        thumb.set_icon()

        self.add_widget_data(thumb, self.row, self.col)
        self.grid_layout.addWidget(thumb, self.row, self.col)

        self.col += 1
        if self.col >= self.col_count:
            self.col = 0
            self.row += 1

        return thumb

    def del_thumb(self, url: str):
        wid = self.url_to_wid.get(url)
        if not wid:
            return
        if wid in self.selected_thumbs:
            self.selected_thumbs.remove(wid)
        self.cell_to_wid.pop((wid.data_item.row, wid.data_item.col))
        self.url_to_wid.pop(url)
        wid.deleteLater()

    def rearrange_thumbs(self):
        super().rearrange_thumbs()
        self.load_visible_thumbs_images()
    
    def deleteLater(self):
        self.watchdog_task.terminate_join()
        for i in self.helpers:
            i.timer.stop()
            i.task.terminate_join()
        return super().deleteLater()
    
    def closeEvent(self, a0):
        self.watchdog_task.terminate_join()
        for i in self.helpers:
            i.timer.stop()
            i.task.terminate_join()
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
            sort_item=self.sort_item,
            urls=urls,
            data_items=data_items
        )
        menu = UMenu(parent=self)
        if self.wid_under_mouse:
            self.base_thumb_actions(menu, item)
        else:
            self.base_grid_actions(menu, item)
        menu.show_under_cursor()
