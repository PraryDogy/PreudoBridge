import os

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QLabel

from cfg import Dynamic, Static
from system.items import BaseItem, MainWinItem
from system.tasks import FinderItems, LoadImages
from system.utils import UThreadPool, Utils

from ._base_widgets import LoadingWid
from .grid import Grid, Thumb


class GridStandart(Grid):
    empty_text = "Нет файлов"
    not_exists_text = "Такой папки не существует"

    def __init__(self, main_win_item: MainWinItem, view_index: int):
        """
        Стандартная сетка виджетов.
        """
        super().__init__(main_win_item, view_index)

        # список url для предотвращения повторной загрузки изображений
        self.loaded_images: list[str] = []
        self.tasks: list[LoadImages] = []

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

        # URunnable FinderItems вернет все элементы из заданной директории
        # где base items это существующие в базе данных записи по элементам
        # а new_items - элементы, записей по которым нет в базе данных
        self.base_items: list[BaseItem] = []
        self.new_items: list[BaseItem] = []

    def load_visible_images(self):
        """
        Составляет список Thumb виджетов, которые находятся в зоне видимости.   
        Запускает загрузку изображений через URunnable
        """
        thumbs: list[Thumb] = []
        for widget in self.main_wid.findChildren(Thumb):
            if not widget.visibleRegion().isEmpty():
                if widget.src not in self.loaded_images:
                    thumbs.append(widget)
        if thumbs:
            for i in self.tasks:
                i.set_should_run(False)
            self.run_load_images_thread(thumbs)

    def force_load_images_cmd(self, urls: list[str]):
        """
        Находит виджеты Thumb по url.   
        Принудительно запускает загрузку изображений через URunnable
        """
        if urls is None:
            return

        thumbs: list[Thumb] = []
        for url in urls:
            wid = self.url_to_wid.get(url)
            if wid:
                thumbs.append(wid)
        self.run_load_images_thread(thumbs)

    def paste_files_fin(self, files: list[str], dest: str):
        super().paste_files_fin(files, dest)
        self.force_load_images_cmd(files)

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
        finder_thread = FinderItems(self.main_win_item, self.sort_item)
        finder_thread.signals_.finished_.connect(self.finalize_finder_items)
        UThreadPool.start(finder_thread)

    def finalize_finder_items(self, items: tuple[list[BaseItem]]):
        """
        Обходит список BaseItem, формируя сетку виджетов Thumb.     
        Делает текст зеленым, если BaseItem есть в списке new_items
        (читай load finder items).    
        Запускает таймер для load visible images
        """
        self.base_items, self.new_items = items

        # испускаем сигнал в MainWin, чтобы нижний бар с отображением пути
        # обновился на актуальный путь
        self.path_bar_update.emit(self.main_win_item.main_dir)

        # высчитываем размер Thumb
        Thumb.calculate_size()

        if not os.path.exists(self.main_win_item.main_dir):
            no_images = QLabel(GridStandart.not_exists_text)
            no_images.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.addWidget(no_images, 0, 0)
            self.loading_lbl.hide()
            self.finished_.emit()
            return

        elif not self.base_items:
            no_images = QLabel(GridStandart.empty_text)
            no_images.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.addWidget(no_images, 0, 0)
            self.loading_lbl.hide()
            self.finished_.emit()
            return

        # создаем иконки на основе расширений, если не было
        exts = {i.type_ for i in self.base_items}
        for ext in exts:
            icon_path = Utils.get_generic_icon_path(ext, Static.GENERIC_ICONS_DIR)
            if icon_path not in Dynamic.generic_icon_paths:
                path_to_svg = Utils.create_generic_icon(ext, icon_path, Static.FILE_SVG)
                Dynamic.generic_icon_paths.append(path_to_svg)

        # испускаем сигнал в MainWin для обновления нижнего бара
        # для отображения "всего элементов"
        self.total_count_update.emit(len(self.base_items))

        # создаем сетку на основе элементов из FinderItems
        self.iter_base_items()

        # если установлен фильтр по рейтингу, запускаем функцию фильтрации,
        # которая скроет из сетки не подходящие под фильтр виджеты
        if Dynamic.rating_filter > 0:
            self.filter_thumbs()

        # если не будет прокрутки, то начнется подгрузка изображений в виджеты
        # в видимой области
        self.load_images_timer.start(100)
        self.finished_.emit()

    def iter_base_items(self):
        self.hide()
        self.col_count = self.get_col_count()
        for base_item in self.base_items:
            thumb = Thumb(base_item.src, base_item.rating)
            thumb.setup_attrs()
            thumb.setup_child_widgets()
            thumb.set_no_frame()
            thumb.set_svg_icon()

            if base_item in self.new_items:
                thumb.set_green_text()

            self.add_widget_data(thumb, self.row, self.col)
            self.grid_layout.addWidget(thumb, self.row, self.col)

            # обновляем данные сетки, чтобы следующие iter base items
            # так же знали актуальные данные сеткик
            self.col += 1
            if self.col >= self.col_count:
                self.col = 0
                self.row += 1

        if self.main_win_item.get_go_to() in self.url_to_wid:
            wid = self.url_to_wid.get(self.main_win_item.get_go_to())
            self.main_win_item.clear_go_to()
            self.select_one_wid(wid)

        elif self.main_win_item.get_urls():
            for i in self.main_win_item.get_urls():
                if i in self.url_to_wid:
                    wid = self.url_to_wid.get(i)
                    self.selected_widgets.append(wid)
                    wid.set_frame()
            self.main_win_item.clear_urls()

        if self.main_win_item.scroll_value:
            QTimer.singleShot(100, self.scroll_value_cmd)

        self.loading_lbl.hide()
        self.show()

    def scroll_value_cmd(self):
            self.verticalScrollBar().setValue(self.main_win_item.scroll_value)
            self.main_win_item.scroll_value = None

    def run_load_images_thread(self, thumbs: list[Thumb]):
        """
        URunnable   
        Запускает загрузку изображений для списка Thumb.    
        Изоражения загружаются из базы данных или берутся из заданной
        директории, если их нет в базе данных.
        """
        # передаем виджеты Thumb из сетки изображений в зоне видимости
        # в URunnable для подгрузки изображений
        # в самом URunnable нет обращений напрямую к Thumb
        # а только испускается сигнал
        task_ = LoadImages(self.main_win_item, thumbs)
        task_.signals_.update_thumb.connect(lambda thumb: self.set_thumb_image(thumb))
        self.tasks.append(task_)
        UThreadPool.start(task_)
    
    def set_thumb_image(self, thumb: Thumb):
        """
        Получает QPixmap из хранилища Thumb.    
        Устанавливает QPixmap в Thumb для отображения в сетке.
        """
        pixmap = thumb.get_pixmap_storage()
        if pixmap:
            try:
                thumb.set_image(pixmap)
                self.loaded_images.append(thumb.src)
            except RuntimeError as e:
                Utils.print_error()

    def set_urls(self):
        """
        Из-за того, что сетка удаляется из MainWin по таймеру,
        нужно вызывать этот метод, чтобы .urls моментально обновились
        для обработки в следующей сетке
        """
        urls = [i.src for i in self.selected_widgets]
        self.main_win_item.set_urls(urls)

    def resizeEvent(self, a0):
        self.loading_lbl.center(self)
        return super().resizeEvent(a0)

    def deleteLater(self):
        for i in self.tasks:
            i.set_should_run(False)
        return super().deleteLater()
    
    def closeEvent(self, a0):
        for i in self.tasks:
            i.set_should_run(False)
        return super().closeEvent(a0)