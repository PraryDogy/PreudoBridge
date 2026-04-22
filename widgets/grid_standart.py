import os

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QLabel

from cfg import Dynamic, JsonData
from system.items import DataItem, DirItem, MainWinItem
from system.tasks import DirScaner, UThreadPool

from .grid import Grid, NoItemsLabel, Thumb


class GridStandart(Grid):
    scroll_timer_ms = 500
    finder_timer_ms = 200
    timeout_timer_ms = 15000

    def __init__(self, main_win_item: MainWinItem, is_grid_search: bool):
        """
        Стандартная сетка виджетов.
        """
        super().__init__(main_win_item, is_grid_search)

        self.tasker = None

        self.scroll_timer = QTimer(self)
        self.scroll_timer.timeout.connect(self.scroll_timer_cmd)
        self.scroll_timer.setSingleShot(True)
        self.verticalScrollBar().valueChanged.connect(self.on_scroll)

    def scroll_timer_cmd(self):
        self.load_visible_thumbs_images()

    def on_scroll(self):
        self.scroll_timer.stop()
        self.scroll_timer.start(self.scroll_timer_ms)

    def start_dir_scaner(self):
        dir_item = DirItem(
            data_items=[],
            main_win_item=self.main_win_item,
            sort_item=self.sort_item
        )
        self.finder_task = DirScaner(dir_item)
        self.finder_task.sigs.finished_.connect(self.finalize_dir_scaner)
        UThreadPool.start(self.finder_task)

    def finalize_dir_scaner(self, dir_item: DirItem):
        if len(dir_item.data_items) == 0:
            self.create_no_items_label(NoItemsLabel.no_files)
            self.load_finished.emit()
            return
        Thumb.calc_size()

        self.path_bar_update.emit(self.main_win_item.abs_current_dir)
        self.total_count_update.emit(
            (len(self.selected_thumbs), len(dir_item.data_items))
        )
        self.create_thumbs(dir_item.data_items)

    def create_thumbs(self, data_items: list[DataItem]):
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
                self.post_process()
                return

            # Создание и настройка виджета
            data_item = self.data_items[self._thumb_index]
            thumb = Thumb(data_item)
            thumb.resize_()
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

    def post_process(self):
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

    
    def deleteLater(self):
        self.finder_task.terminate_join()
        return super().deleteLater()
    
    def closeEvent(self, a0):
        self.finder_task.terminate_join()
        return super().closeEvent(a0)
