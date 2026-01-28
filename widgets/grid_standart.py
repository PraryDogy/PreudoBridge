import os
import time

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QFrame, QLabel, QVBoxLayout

from cfg import Dynamic, Static
from system.items import DataItem, MainWinItem
from system.multiprocess import ProcessWorker, FinderItemsLoader

from .grid import Grid, NoItemsLabel, Thumb
from .warn_win import WinWarn


class LoadingWidget(QLabel):
    def __init__(self, text="Загрузка…", parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(f"""
            font-size: 15px;
        """)
        self.adjustSize()


class GridStandart(Grid):

    def __init__(self, main_win_item: MainWinItem, is_grid_search: bool):
        """
        Стандартная сетка виджетов.
        """
        super().__init__(main_win_item, is_grid_search)

        self.tasker = None

        self.load_vis_images_timer = QTimer(self)
        self.load_vis_images_timer.timeout.connect(self.load_visible_thumbs_images)
        self.load_vis_images_timer.setSingleShot(True)
        self.verticalScrollBar().valueChanged.connect(self.on_scroll)

        self.loading_label = LoadingWidget()
        QTimer.singleShot(1, self.show_loading_label)

    def show_loading_label(self):
        try:
            self.loading_label.setParent(self.viewport())
        except RuntimeError:
            return
        vp = self.viewport().rect()
        lbl = self.loading_label.rect()

        self.loading_label.move(
            (vp.width() - lbl.width()) // 2,
            (vp.height() - lbl.height()) // 2
        )

        self.loading_label.show()

    def on_scroll(self):
        self.load_vis_images_timer.stop()
        self.load_vis_images_timer.start(1000)

    def start_load_finder_items(self):

        def timeout_task():
            self.finder_timer.stop()
            self.finder_task.terminate()
            poll_task_fin(
                {"path": "", "data_items": []}
            )

        def poll_task_fin(result: dict):
            self.fin_load_finder_items(result)

        def poll_task():
            q = self.finder_task.get_queue()

            if not q.empty():
                result = q.get()
                poll_task_fin(result)

            elif not self.finder_task.proc.is_alive():
                self.finder_timer.stop()
                self.timeout_timer.stop()
                self.finder_task.terminate()

        self.finder_task = ProcessWorker(
            target=FinderItemsLoader.start,
            args=(self.main_win_item, self.sort_item)
        )
        self.finder_task.start()

        self.finder_timer = QTimer(self)
        self.finder_timer.timeout.connect(poll_task)
        self.finder_timer.start(200)

        self.timeout_timer = QTimer(self)
        self.timeout_timer.timeout.connect(timeout_task)
        self.timeout_timer.start(15000)

    def fin_load_finder_items(self, result):
        fixed_path = result["path"]
        data_items = result["data_items"]

        if fixed_path:
            self.main_win_item.main_dir = fixed_path
        else:
            self.create_no_items_label(NoItemsLabel.no_conn)
            self.mouseMoveEvent = lambda args: None
            self.load_finished.emit()
            self.loading_label.hide()
            return

        Thumb.calc_size()
        if len(data_items) == 0:
            self.create_no_items_label(NoItemsLabel.no_files)
            self.load_finished.emit()
            self.loading_label.hide()
            return

        self.path_bar_update.emit(self.main_win_item.main_dir)
        self.total_count_update.emit((len(self.selected_thumbs), len(data_items)))
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

        add_one_thumb()

    def create_thumbs_fin(self):

        def select_delayed(wid: Thumb):
            self.select_single_thumb(wid)
            self.ensureWidgetVisible(wid)

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
        self.load_finished.emit()
        self.loading_label.hide()
        QTimer.singleShot(10, self.load_visible_thumbs_images)

    def mousePressEvent(self, a0):
        if self.loading_label.isVisible():
            return    
        return super().mousePressEvent(a0)

    def keyPressEvent(self, a0):
        if self.loading_label.isVisible():
            return    
        return super().keyPressEvent(a0)

    def contextMenuEvent(self, a0):
        if self.loading_label.isVisible():
            return    
        return super().contextMenuEvent(a0)

    def mouseMoveEvent(self, a0):
        if self.loading_label.isVisible():
            return  
        return super().mouseMoveEvent(a0)
    
    def deleteLater(self):
        try:
            self.finder_timer.stop()
            self.finder_task.terminate()
        except AttributeError:
            ...
        return super().deleteLater()
    
    def closeEvent(self, a0):
        try:
            self.finder_timer.stop()
            self.finder_task.terminate()
        except AttributeError:
            ...
        return super().closeEvent(a0)
