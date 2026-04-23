import os

from PyQt5.QtCore import QRect, QSize, Qt, QTimer
from PyQt5.QtWidgets import QLabel
from watchdog.events import FileSystemEvent

from cfg import Dynamic, Static
from system.items import ClipboardItemGlob, DataItem, DirItem, MainWinItem
from system.multiprocess import ImgLoader, ProcessWorker, WatchdogTask
from system.tasks import DirScaner, QImagesCreator, UThreadPool

from .grid import Grid, NoItemsLabel, Thumb
from .win_rename import WinRename


class GridStandart(Grid):
    scroll_timer_ms = 500
    finder_timer_ms = 200
    timeout_timer_ms = 15000

    def __init__(self, main_win_item: MainWinItem, is_grid_search: bool):
        super().__init__(main_win_item, is_grid_search)
        self.setAcceptDrops(True)
        self.watchdog_modified_files = set()
        self.process_timer_dict: dict[ProcessWorker, QTimer] = {}
        self.scroll_timer = QTimer(self)
        self.scroll_timer.timeout.connect(self.load_visible_thumbs_images)
        self.scroll_timer.setSingleShot(True)
        self.verticalScrollBar().valueChanged.connect(self.on_scroll)
        self.watchdog_start()

    def on_scroll(self):
        self.scroll_timer.stop()
        self.scroll_timer.start(self.scroll_timer_ms)

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
            self._start_load_images_task(thumbs)

    def _start_load_images_task(self, thumbs: list[Thumb]):
        """
        Запускает фоновую задачу загрузки изображений для списка Thumb.
        Изображения загружаются из базы данных или из директории, если в БД нет.
        """

        def update_thumbs(data_items: list[DataItem]):
            for i in data_items:
                thumb = self.url_to_wid[i.abs_path]
                thumb.data_item.qimages.update(i.qimages)
                thumb.set_image()

        def load_qimages(data_items: list[DataItem]):
            task = QImagesCreator(data_items)
            task.sigs.finished_.connect(update_thumbs)
            UThreadPool.start(task)

        def poll_task(img_task: ProcessWorker, img_timer: QTimer):
            img_timer.stop()
            data_items: list[DataItem] = []
            while not img_task.queue.empty():
                data_items.append(img_task.queue.get())
            load_qimages(data_items)
            if not img_task.is_alive() and img_task.queue.empty():
                img_task.terminate_join()
            else:
                img_timer.start(self.img_timer_ms)

        img_task = ProcessWorker(
            target=ImgLoader.start,
            args=([i.data_item for i in thumbs], self.main_win_item, )
        )

        img_timer = QTimer(self)
        img_timer.setSingleShot(True)
        img_timer.timeout.connect(lambda: poll_task(img_task, img_timer))
        self.process_timer_dict[img_task] = img_timer
        img_task.start()
        img_timer.start(self.img_timer_ms)

    def dir_scaner_start(self):
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

        self.path_bar_update.emit(self.main_win_item.abs_current_dir)
        self.total_count_update.emit(
            (len(self.selected_thumbs), len(dir_item.data_items))
        )
        self.create_thumbs_start(dir_item.data_items)

    def create_thumbs_start(self, data_items: list[DataItem]):
        self.col_count = self.get_clmn_count()
        self._thumb_index = 0
        self.data_items = data_items
        self.row = 0
        self.col = 0

        def add_one_thumb():
            if self._thumb_index >= len(self.data_items):
                # Все виджеты добавлены
                self.data_items = None
                self._thumb_index = 0
                self.create_thumbs_end()
                return

            # Создание и настройка виджета
            data_item = self.data_items[self._thumb_index]
            thumb = Thumb(data_item)
            thumb.update_all(self.sort_item)
            thumb.set_no_frame()
            thumb.set_icon()

            # Добавление в layout и внутренние структуры
            self.add_widget_data(thumb, self.row, self.col)
            self.grid_layout.addWidget(thumb, self.row, self.col)

            # Обновление позиции в сетке
            self.col += 1
            if self.col >= self.col_count:
                self.col = 0
                self.row += 1

            self._thumb_index += 1

            # Планируем добавление следующего виджета
            QTimer.singleShot(0, add_one_thumb)

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

    def new_folder(self):
        def fin(name: str):
            try:
                os.mkdir(
                    os.path.join(self.main_win_item.abs_current_dir, name)
                )
            except Exception as e:
                ...
        self.rename_win = WinRename(self.new_folder_text)
        self.rename_win.center(self.window())
        self.rename_win.finished_.connect(lambda name: fin(name))
        self.rename_win.show()

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
        for proc, timer in self.process_timer_dict.items():
            timer.stop()
            proc.terminate_join()
        return super().deleteLater()
    
    def closeEvent(self, a0):
        self.watchdog_task.terminate_join()
        for proc, timer in self.process_timer_dict.items():
            timer.stop()
            proc.terminate_join()
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