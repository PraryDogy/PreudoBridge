import os
import time

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QFrame, QLabel, QVBoxLayout

from cfg import Dynamic, Static
from system.items import DataItem, MainWinItem
from system.tasks import FinderItemsLoader, UThreadPool
from system.utils import Utils

from .grid import Grid, NoItemsLabel, Thumb


class LoadingWidget(QFrame):
    def __init__(self):
        super().__init__()
        label = QLabel("Загрузка…")
        label.setAlignment(Qt.AlignCenter)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.addWidget(label)

        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(f"""
            background: {Static.rgba_gray};
            border-radius: 7px;
            font-size: 14px;
        """)

        self.adjustSize()


class GridStandart(Grid):

    def __init__(self, main_win_item: MainWinItem, is_grid_search: bool):
        """
        Стандартная сетка виджетов.
        """
        super().__init__(main_win_item, is_grid_search)

        self.load_vis_images_timer = QTimer(self)
        self.load_vis_images_timer.timeout.connect(self.load_visible_thumbs_images)
        self.load_vis_images_timer.setSingleShot(True)
        self.verticalScrollBar().valueChanged.connect(self.on_scroll)

        self.loading_wid = LoadingWidget()
        self.loading_timer = QTimer(self)
        self.loading_timer.setSingleShot(True)
        self.loading_timer.timeout.connect(self.show_loading_label)
        self.loading_timer.start(500)

        self.timeout_timer = QTimer(self)
        self.timeout_timer.setSingleShot(True)
        self.timeout_timer.timeout.connect(self.check_load_finder_time)

    def show_loading_label(self):
        vp = self.viewport()
        self.loading_wid.setParent(vp)

        center = vp.rect().center()
        self.loading_wid.move(center - self.loading_wid.rect().center())
        self.loading_wid.show()

    def stop_loading_label(self):
        self.loading_timer.stop()
        self.loading_wid.deleteLater()
    
    def on_scroll(self):
        self.load_vis_images_timer.stop()
        self.load_vis_images_timer.start(1000)

    def check_load_finder_time(self, limit: int = 1 * 60):
        current = time.time()
        if current - self.finder_items_task.start_time > limit:
            print("задача зависла")
        else:
            self.timeout_timer.start(1000)

    def start_load_finder_items(self):
        self.finder_items_task = FinderItemsLoader(self.main_win_item, self.sort_item)
        self.finder_items_task.sigs.finished_.connect(
            lambda result: self.fin_load_finder_items(result)
        )
        UThreadPool.start(self.finder_items_task)
        self.timeout_timer.start(1000)

    def fin_load_finder_items(self, result):
        self.timeout_timer.stop()
        fixed_path = result["path"]
        data_items = result["data_items"]

        if fixed_path:
            self.main_win_item.main_dir = fixed_path
        else:
            self.stop_loading_label()
            self.create_no_items_label(NoItemsLabel.no_conn)
            self.mouseMoveEvent = lambda args: None
            self.load_finished.emit()
            return

        Thumb.calc_size()
        if len(data_items) == 0:
            self.stop_loading_label()
            self.create_no_items_label(NoItemsLabel.no_files)
            self.load_finished.emit()
            return

        self.path_bar_update.emit(self.main_win_item.main_dir)
        self.total_count_update.emit((len(self.selected_thumbs), len(data_items)))
        self.load_finished.emit()
        self.create_thumbs(data_items)

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
                self.show()
                self.create_thumbs_fin()
                return

            # Создание и настройка виджета
            data_item = self.data_items[self._thumb_index]
            thumb = Thumb(data_item)
            thumb.resize_()
            thumb.set_no_frame()
            thumb.set_uti_data()

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

        self.grid_wid.hide()
        add_one_thumb()

    def create_thumbs_fin(self):

        def select_delayed(wid: Thumb):
            self.select_single_thumb(wid)
            self.ensureWidgetVisible(wid)

        self.stop_loading_label()
        self.grid_wid.show()
        if self.main_win_item.get_go_to() in self.url_to_wid:
            wid = self.url_to_wid.get(self.main_win_item.get_go_to())
            self.main_win_item.clear_go_to()
            self.total_count_update.emit((len(self.selected_thumbs), len(self.cell_to_wid)))
            QTimer.singleShot(300, lambda: select_delayed(wid))
        elif self.main_win_item.get_urls_to_select():
            for i in self.main_win_item.get_urls_to_select():
                if i in self.url_to_wid:
                    wid = self.url_to_wid.get(i)
                    self.selected_thumbs.append(wid)
                    wid.set_frame()
            if self.selected_thumbs:
                wid = self.selected_thumbs[-1]
            self.main_win_item.clear_urls_to_select()
        # если установлен фильтр по рейтингу, запускаем функцию фильтрации,
        # которая скроет из сетки не подходящие под фильтр виджеты
        if Dynamic.rating_filter > 0 or Dynamic.word_filters:
            self.filter_thumbs()
        self.rearrange_thumbs()
        QTimer.singleShot(100, self.load_visible_thumbs_images)

    def resizeEvent(self, a0):
        return super().resizeEvent(a0)
    
    def deleteLater(self):
        return super().deleteLater()
    
    def closeEvent(self, a0):
        return super().closeEvent(a0)
