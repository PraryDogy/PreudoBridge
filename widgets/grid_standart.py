import os
from dataclasses import dataclass
from time import perf_counter

from PyQt6.QtCore import QTimer, Qt
from watchdog.events import FileSystemEvent

from cfg import Static
from system.items import (ClipboardItemGlob, DataItem, DirItem, MainWinItem,
                          TotalCountItem)
from system.multiprocess import ImgLoader, ProcessWorker, WatchdogTask
from system.shared_utils import ImgUtils
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
        self.watchdog_modified_files: set[str] = set()
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

    # ------------------------------------------------------------------
    # watchdog: события файловой системы
    # ------------------------------------------------------------------
    def watchdog_start(self, fast_ms=300, slow_ms=1000):

        def poll_task():
            ms = slow_ms if ClipboardItemGlob.src_urls else fast_ms
            try:
                events: list[FileSystemEvent] = []
                while not self.watchdog_task.queue.empty():
                    events.append(self.watchdog_task.queue.get())
                if events:
                    for ev in events:
                        try:
                            self.watchdog_apply(ev)
                        except Exception:
                            Utils.print_error()
                    # тексты и размеры уже актуальны, пересчитываем только порядок
                    self.sort(update_text=False)
                    self.rearrange_thumbs()
            finally:
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
        path = e.src_path
        wid: Thumb | None = self.url_to_wid.get(path)

        if e.event_type == "deleted":
            self.del_thumb(path)
            if wid and wid.data_item.is_selected:
                self.watchdog_modified_files.add(path)

        elif e.event_type == "created":
            self.del_thumb(path)  # защита от дубликатов
            new_thumb = self.new_thumb(path)
            if path in self.watchdog_modified_files:
                self.select_multiple_thumb(new_thumb)
                self.watchdog_modified_files.discard(path)

        elif e.event_type == "moved":
            dest = e.dest_path
            self.del_thumb(path)
            self.del_thumb(dest)  # если dest уже был в сетке
            new_thumb = self.new_thumb(dest)
            if wid and wid.data_item.is_selected:
                self.select_multiple_thumb(new_thumb)

        self.update_empty_label()

    def update_empty_label(self):
        self.no_items_label_remove()
        if not self.url_to_wid:
            self.no_items_label_create(NoItemsLabel.no_files)

    def new_thumb(self, url: str) -> Thumb:
        data = DataItem(url)
        data.set_properties()
        data.must_hidden = not self.passes_filter(data)
        thumb = Thumb(data)
        thumb.set_text_and_size(self.main_win_item.sort_item)
        thumb.set_no_frame()
        thumb.set_common_icon()
        # место в сетке назначает rearrange() после sort(), здесь не трогаем cell_to_wid
        self.url_to_wid[data.abs_path] = thumb
        return thumb

    # ------------------------------------------------------------------
    # ленивая загрузка превью
    # ------------------------------------------------------------------
    def get_visible_thumbs(self) -> list[Thumb]:
        top = self.verticalScrollBar().value()
        bottom = top + self.viewport().height()
        return [
            wid for wid in self.cell_to_wid.values()
            if not (wid.y() + wid.height() < top or wid.y() > bottom)
        ]

    def load_visible_thumbs(self):
        if not self.grid_wid.isVisible():
            return
        to_load = [
            wid for wid in self.get_visible_thumbs()
            if wid.data_item.type_ != Static.folder_type
            and not wid.data_item.qimages
        ]
        if to_load:
            self.img_loader_start(to_load)

    def img_loader_start(self, thumbs: list[Thumb], sec=0.004):
        # один активный загрузчик: новый запрос заменяет предыдущий
        self.stop_img_loader_tasks()

        def process_item(item: DataItem):
            thumb = self.url_to_wid.get(item.abs_path)
            if thumb is None or thumb.data_item.qimages:
                return
            src = Utils.qimage_from_array(item._img_array)
            if src is None:
                return
            qimages = {"src": src}
            for size in Static.thumb_widget_pixmap_size:
                # чтобы вмещалось в квадратик
                qimages[size] = Utils.scaled(src, size - 5)
            thumb.data_item.qimages.update(qimages)
            thumb.data_item.qimages_loaded = True
            thumb.set_pixmap_with_actual_size()

        def poll_task(helper: ImgLoaderHelper):
            helper.timer.stop()
            start = perf_counter()
            try:
                while not helper.task.queue.empty():
                    process_item(helper.task.queue.get())
                    if perf_counter() - start > sec:
                        break
            except Exception:
                # битый элемент не должен останавливать весь загрузчик
                Utils.print_error()
            if not helper.task.is_alive() and helper.task.queue.empty():
                helper.task.terminate_join()
                self.helpers = [h for h in self.helpers if h is not helper]
            else:
                helper.timer.start(0)

        img_task = ProcessWorker(
            target=ImgLoader.start,
            args=([i.data_item for i in thumbs], self.main_win_item, )
        )
        img_timer = QTimer(self)
        helper = ImgLoaderHelper(task=img_task, timer=img_timer)
        img_timer.setSingleShot(True)
        img_timer.timeout.connect(lambda: poll_task(helper))
        self.helpers.append(helper)
        img_task.start()
        img_timer.start(0)

    def stop_img_loader_tasks(self):
        for i in self.helpers:
            i.timer.stop()
            QTimer.singleShot(0, i.task.terminate_join)
        self.helpers.clear()

    # ------------------------------------------------------------------
    # сканирование папки
    # ------------------------------------------------------------------
    def dir_scaner_start(self):
        dir_item = DirItem(
            data_items=[],
            main_win_item=self.main_win_item
        )
        self.finder_task = DirScaner(dir_item)
        self.finder_task.sigs.finished_.connect(self.dir_scaner_end)
        UThreadPool.start(self.finder_task)

    def dir_scaner_end(self, dir_item: DirItem):
        total = len(dir_item.data_items)
        self.bar_path_update.emit(self.main_win_item.abs_current_dir)
        self.total_count_update.emit(
            TotalCountItem(selected=len(self.selected_thumbs), total=total)
        )
        if total == 0:
            self.no_items_label_create(NoItemsLabel.no_files)
            return
        Thumb.calculate_size()
        self.create_thumbs(dir_item.data_items)
        self.select_thumbs()
        QTimer.singleShot(0, self.rearrange_thumbs)

    def create_thumbs(self, data_items: list[DataItem]):
        for data_item in data_items:
            data_item.must_hidden = not self.passes_filter(data_item)
            thumb = Thumb(data_item)
            thumb.set_text_and_size(self.main_win_item.sort_item)
            thumb.set_no_frame()
            thumb.set_common_icon()
            # cell_to_wid заполняет rearrange(), здесь только url_to_wid
            self.url_to_wid[data_item.abs_path] = thumb

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

    def rearrange_thumbs(self):
        super().rearrange()
        self.load_visible_thumbs()

    # ------------------------------------------------------------------
    # контекстное меню
    # ------------------------------------------------------------------
    def grid_actions(self):
        self.context_menu.add_action(
            action=self.context_actions.new_folder,
            callback=lambda: self.base_signals.new_folder.emit()
        )
        if ClipboardItemGlob.src_dir:
            self.context_menu.add_action(
                action=self.context_actions.paste_files,
                callback=lambda: self.paste_files.emit()
            )
        self.context_menu.addSeparator()

        self.folder_actions()
        self.context_menu.addSeparator()

        self.context_menu.addSeparator()
        super().base_grid_actions()

    def contextMenuEvent(self, a0):
        super().contextMenuEvent(a0)
        if self.wid_under_mouse:
            self.base_thumb_actions()
        else:
            self.grid_actions()
        self.context_menu.show_under_mouse()

    # ------------------------------------------------------------------
    # жизненный цикл
    # ------------------------------------------------------------------
    def deleteLater(self):
        self.watchdog_task.terminate_join()
        self.stop_img_loader_tasks()
        return super().deleteLater()

    def closeEvent(self, a0):
        self.watchdog_task.terminate_join()
        self.stop_img_loader_tasks()
        return super().closeEvent(a0)

    # ------------------------------------------------------------------
    # drag-and-drop и клавиатура
    # ------------------------------------------------------------------
    def dragEnterEvent(self, a0):
        if a0.mimeData().hasUrls():
            a0.acceptProposedAction()
        return super().dragEnterEvent(a0)

    def dropEvent(self, a0):
        if not a0.mimeData().hasUrls():
            return
        urls = [
            i.toLocalFile().rstrip(os.sep)
            for i in a0.mimeData().urls()
        ]
        urls = [i for i in urls if i.endswith(ImgUtils.ext_all)]
        if not urls:
            return
        src = os.path.dirname(urls[0])
        if src == self.main_win_item.abs_current_dir:
            print("нельзя копировать в себя через DropEvent")
            return
        ClipboardItemGlob.src_dir = src
        ClipboardItemGlob.src_urls = urls
        # перетаскивание всегда копирует: сбрасываем залипший флаг "вырезать"
        ClipboardItemGlob.set_is_cut(False)
        self.paste_files.emit()
        return super().dropEvent(a0)

    def keyPressEvent(self, a0):
        # раньше обычный V тоже вставлял файлы: нужен именно Ctrl+V
        if (
            a0.key() == Qt.Key.Key_V
            and a0.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            if ClipboardItemGlob.src_urls:
                self.paste_files.emit()
            return
        return super().keyPressEvent(a0)
