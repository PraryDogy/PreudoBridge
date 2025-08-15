import os

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QLabel

from cfg import Dynamic, Static
from system.items import BaseItem, MainWinItem
from system.tasks import FinderItems, NewItems
from system.utils import UThreadPool, Utils

from ._base_widgets import LoadingWid
from .grid import Grid, Thumb


class GridStandart(Grid):
    empty_text = "Нет файлов"
    not_exists_text = "Такой папки не существует. \nВозможно не подключен сетевой диск."

    def __init__(self, main_win_item: MainWinItem):
        """
        Стандартная сетка виджетов.
        """
        super().__init__(main_win_item)

        # при скроллинге запускается данный таймер и сбрасывается предыдуший
        # только при остановке скроллинга спустя время запускается
        # функция загрузки изображений
        self.load_images_timer = QTimer(self)
        self.load_images_timer.setSingleShot(True)
        self.load_images_timer.timeout.connect(self.load_visible_images)
        self.verticalScrollBar().valueChanged.connect(self.on_scroll_changed)

        # виджет поверх остальных с текстом "загрузка"
        self.loading_lbl = LoadingWid(self)
        self.loading_lbl.center(self)
    
    def update_mod_thumbs(self):
        thumbs = super().update_mod_thumbs()
        self.start_load_images_task(thumbs)

    def on_scroll_changed(self, value: int):
        """
        - При сколлинге запускается таймер    
        - Запускается load visible images
        - Если скролл достиг низа, подгрузить следующие limit айтемов
        """
        self.load_images_timer.stop()
        self.load_images_timer.start(1000)

    def load_finder_items(self):
        """
        URunnable   
        Обходит заданную директорию os scandir.      
        Генерирует на основе содержимого директории список BaseItem.    
        Проверяет на наличие BaseItem в базе данных.          
        Загружает рейтинг BaseItem из базы данных, если имеется.     
        Испускает сигнал finished_, который содержит кортеж:
        - список всех BaseItem
        - список новых BaseItem, которых не было в базе данных
        """
        finder_items_task = FinderItems(self.main_win_item, self.sort_item)
        finder_items_task.sigs.finished_.connect(lambda base_items: self.finalize_finder_items(base_items))
        UThreadPool.start(finder_items_task)

    def finalize_finder_items(self, base_items: tuple[list[BaseItem]]):
        """
        Обходит список BaseItem, формируя сетку виджетов Thumb.     
        Делает текст зеленым, если BaseItem есть в списке new_items
        (читай load finder items).    
        Запускает таймер для load visible images
        """
        # испускаем сигнал в MainWin, чтобы нижний бар с отображением пути
        # обновился на актуальный путь
        self.path_bar_update.emit(self.main_win_item.main_dir)

        # высчитываем размер Thumb
        Thumb.calc_size()

        if not os.path.exists(self.main_win_item.main_dir):
            no_images = QLabel(GridStandart.not_exists_text)
            no_images.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.addWidget(no_images, 0, 0)
            self.loading_lbl.hide()
            self.finished_.emit()
            return

        elif not base_items:
            no_images = QLabel(GridStandart.empty_text)
            no_images.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.addWidget(no_images, 0, 0)
            self.loading_lbl.hide()
            self.finished_.emit()
            return

        # создаем иконки на основе расширений, если не было
        exts = {i.type_ for i in base_items}
        for ext in exts:
            icon_path = Utils.get_generic_icon_path(ext, Static.GENERIC_ICONS_DIR)
            if icon_path not in Dynamic.generic_icon_paths:
                path_to_svg = Utils.create_generic_icon(ext, icon_path, Static.FILE_SVG)
                Dynamic.generic_icon_paths.append(path_to_svg)

        # испускаем сигнал в MainWin для обновления нижнего бара
        # для отображения "всего элементов"
        self.total_count_update.emit((len(self.selected_thumbs), len(base_items)))

        self.hide()
        # создаем сетку на основе элементов из FinderItems
        self.create_thumbs_grid(base_items)
        self.loading_lbl.hide()
        self.show()

    def create_thumbs_grid(self, base_items: list[BaseItem]):
        self.col_count = self.get_clmn_count()
        self._thumb_index = 0
        self._batch_limit = 50
        self._thumb_items = base_items

        def add_batch():
            count = 0
            while self._thumb_index < len(self._thumb_items) and count < self._batch_limit:
                base_item = self._thumb_items[self._thumb_index]
                thumb = Thumb(base_item.src, base_item.rating)
                thumb.migrate_from_base_item(base_item)
                thumb.set_widget_size()
                thumb.set_no_frame()
                thumb.set_generic_icon()
                self.add_widget_data(thumb, self.row, self.col)
                self.grid_layout.addWidget(thumb, self.row, self.col)

                self.col += 1
                if self.col >= self.col_count:
                    self.col = 0
                    self.row += 1

                self._thumb_index += 1
                count += 1

            if self._thumb_index < len(self._thumb_items):
                QTimer.singleShot(50, add_batch)
            else:
                self._thumb_items = None
                self._thumb_index = 0
                self._post_grid_selection()

        add_batch()

    def _post_grid_selection(self):
        def select_delayed(wid: Thumb):
            self.select_single_thumb(wid)
            self.ensureWidgetVisible(wid)

        if self.main_win_item.get_go_to() in self.url_to_wid:
            wid = self.url_to_wid.get(self.main_win_item.get_go_to())
            self.main_win_item.clear_go_to()
            self.total_count_update.emit((len(self.selected_thumbs), len(self.cell_to_wid)))
            QTimer.singleShot(30, lambda: select_delayed(wid))
        elif self.main_win_item.get_urls_to_select():
            for i in self.main_win_item.get_urls_to_select():
                if i in self.url_to_wid:
                    wid = self.url_to_wid.get(i)
                    self.selected_thumbs.append(wid)
                    wid.set_frame()
            if self.selected_thumbs:
                wid = self.selected_thumbs[-1]
                QTimer.singleShot(30, lambda: self.ensureWidgetVisible(wid))
            self.main_win_item.clear_urls_to_select()

        # если установлен фильтр по рейтингу, запускаем функцию фильтрации,
        # которая скроет из сетки не подходящие под фильтр виджеты
        if Dynamic.rating_filter > 0:
            self.filter_thumbs()
            self.rearrange_thumbs()

        # если не будет прокрутки, то начнется подгрузка изображений в виджеты
        # в видимой области
        self.load_images_timer.start(100)
        self.finished_.emit()

    def resizeEvent(self, a0):
        self.loading_lbl.center(self)
        return super().resizeEvent(a0)
