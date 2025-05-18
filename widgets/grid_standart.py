import os

import numpy as np
from PyQt5.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QLabel
from sqlalchemy import (Connection, Insert, RowMapping, Update, insert, select,
                        update)

from cfg import Dynamic, Static, ThumbData
from database import CACHE, ColumnNames, Dbase
from utils import FitImg, Utils

from ._base_items import BaseItem, MainWinItem, URunnable, UThreadPool
from .finder_items import FinderItems, LoadingWid
from .grid import Grid, Thumb


class AnyBaseItem:
    @classmethod
    def check_db_record(cls, conn: Connection, thumb: Thumb) -> tuple[Insert | None, None]:
        if not cls.load_db_record(conn, thumb):
            return cls.insert_new_record(conn, thumb)
        else:
            return (None, None)

    @classmethod
    def load_db_record(cls, conn: Connection, thumb: Thumb):
        stmt = select(CACHE.c.id)
        stmt = stmt.where(CACHE.c.name == Utils.get_hash_filename(thumb.name))
        res_by_src = Dbase.execute_(conn, stmt).mappings().first()
        if res_by_src:
            return True
        else:
            return False

    @classmethod
    def insert_new_record(cls, conn: Connection, thumb: Thumb) -> tuple[Insert, None]:
        """
        Новая запись в базу данных.
        """
        new_name = Utils.get_hash_filename(filename=thumb.name)

        values = {
            ColumnNames.NAME: new_name,
            ColumnNames.TYPE: thumb.type_,
            ColumnNames.RATING: 0,
        }

        stmt = insert(CACHE).values(**values)
        return (stmt, None)


class ImageBaseItem:
    @classmethod
    def get_pixmap(cls, conn: Connection, thumb: Thumb) -> tuple[Update | Insert| None, QPixmap]:
        stmt, img_array = cls.get_img_array(conn, thumb)
        return (stmt, Utils.pixmap_from_array(img_array))

    @classmethod
    def get_img_array(cls, conn: Connection, thumb: Thumb) -> tuple[Update | Insert| None, np.ndarray]:
        stmt = select(
            CACHE.c.id,
            CACHE.c.img,
            CACHE.c.size,
            CACHE.c.mod,
            CACHE.c.rating
        )

        stmt = stmt.where(
            CACHE.c.name == Utils.get_hash_filename(thumb.name)
        )
        res_by_name = Dbase.execute_(conn, stmt)
        res_by_name = res_by_name.mappings().first()
        if res_by_name:
            if res_by_name.get(ColumnNames.MOD) != int(thumb.mod):
                # print("даты не совпадают", res_by_name.get(ColumnNames.MOD), thumb.mod)
                return cls.update_db_record(thumb, res_by_name.get(ColumnNames.ID))
            else:
                # print("ok", thumb.src)
                return cls.old_db_record(res_by_name)
        else:
            # print("new_record", thumb.src)
            return cls.insert_db_record(thumb)
    
    @classmethod
    def old_db_record(cls, res_by_name: RowMapping) -> tuple[None, np.ndarray]:
        bytes_img = Utils.bytes_to_array(res_by_name.get(ColumnNames.IMG))
        return (None, bytes_img)

    @classmethod
    def update_db_record(cls, thumb: Thumb, row_id: int) -> tuple[Update, np.ndarray]:
        img_array = cls.get_small_ndarray_img(thumb.src)
        bytes_img = Utils.numpy_to_bytes(img_array)
        new_size, new_mod, new_resol = cls.get_stats(thumb.src, img_array)
        new_name = Utils.get_hash_filename(filename=thumb.name)
        partial_hash = Utils.get_partial_hash(file_path=thumb.src)
        values = {
            ColumnNames.NAME: new_name,
            ColumnNames.IMG: bytes_img,
            ColumnNames.SIZE: new_size,
            ColumnNames.MOD: new_mod,
            ColumnNames.RESOL: new_resol,
            ColumnNames.PARTIAL_HASH: partial_hash
        }
        stmt = update(CACHE).where(CACHE.c.id == row_id)
        stmt = stmt.values(**values)
        return (stmt, img_array)

    @classmethod
    def insert_db_record(cls, thumb: Thumb) -> tuple[Insert, np.ndarray]:
        img_array = cls.get_small_ndarray_img(thumb.src)
        bytes_img = Utils.numpy_to_bytes(img_array)
        new_size, new_mod, new_resol = cls.get_stats(thumb.src, img_array)
        new_name = Utils.get_hash_filename(filename=thumb.name)
        partial_hash = Utils.get_partial_hash(file_path=thumb.src)
        values = {
            ColumnNames.IMG: bytes_img,
            ColumnNames.NAME: new_name,
            ColumnNames.TYPE: thumb.type_,
            ColumnNames.SIZE: new_size,
            ColumnNames.MOD: new_mod,
            ColumnNames.RATING: 0,
            ColumnNames.RESOL: new_resol,
            ColumnNames.CATALOG: "",
            ColumnNames.PARTIAL_HASH: partial_hash
        }
        stmt = insert(CACHE).values(**values)
        return (stmt, img_array)
    
    @classmethod
    def get_small_ndarray_img(cls, src: str) -> np.ndarray:
        img_array = Utils.read_image(src)
        img_array = FitImg.start(img_array, ThumbData.DB_IMAGE_SIZE)
        return img_array
    
    @classmethod
    def get_stats(cls, src: str, img_array: np.ndarray):
        """
        Возвращает: размер, дату изменения, разрешение
        """
        try:
            stats = os.stat(src)
            height, width = img_array.shape[:2]
            new_size = int(stats.st_size)
            new_mod = int(stats.st_mtime)
            new_resol = f"{width}x{height}"
            return new_size, new_mod, new_resol
        except Exception as e:
            Utils.print_error(e)
            return 0, 0, ""


class WorkerSignals(QObject):
    update_thumb = pyqtSignal(BaseItem)
    finished_ = pyqtSignal()


class LoadImages(URunnable):
    def __init__(self, main_win_item: MainWinItem, thumbs: list[Thumb]):
        """
        URunnable   
        Сортирует список Thumb по размеру по возрастанию для ускорения загрузки
        Загружает изображения из базы данных или создает новые
        """
        super().__init__()
        self.signals_ = WorkerSignals()
        self.main_win_item = main_win_item
        self.stmt_list: list[Insert | Update] = []
        self.thumbs = thumbs
        key_ = lambda x: x.size
        self.thumbs.sort(key=key_)

    def task(self):
        """
        Создает подключение к базе данных   
        Запускает обход списка Thumb для загрузки изображений   
        Испускает сигнал finished_
        """
        if not self.thumbs:
            return

        db = os.path.join(self.main_win_item.main_dir, Static.DB_FILENAME)
        self.dbase = Dbase()
        engine = self.dbase.create_engine(db)

        if engine is None:
            return

        self.conn = Dbase.open_connection(engine)
        self.process_thumbs()
        self.process_stmt_list()

        Dbase.close_connection(self.conn)
        try:
            self.signals_.finished_.emit()
        except RuntimeError as e:
            Utils.print_error(e)

    def process_thumbs(self):
        """
        Обходит циклом список Thumb     
        Пытается загрузить изображение из базы данных или создает новое,
        чтобы передать его в Thumb
        """
        for base_item in self.thumbs:
            if not self.is_should_run():
                return  
            if base_item.type_ not in Static.ext_all:
                stmt, _ = AnyBaseItem.check_db_record(self.conn, base_item)
                if isinstance(stmt, Insert):
                    self.stmt_list.append(stmt)
            else:
                stmt, pixmap = ImageBaseItem.get_pixmap(self.conn, base_item)
                base_item.set_pixmap_storage(pixmap)
                if isinstance(stmt, (Insert, Update)):
                    self.stmt_list.append(stmt)
                try:
                    self.signals_.update_thumb.emit(base_item)
                except (TypeError, RuntimeError) as e:
                    Utils.print_error(e)
                    return
                
    def process_stmt_list(self):
        for stmt in self.stmt_list:
            if not Dbase.execute_(self.conn, stmt):
                return
        Dbase.commit_(self.conn)

class GridStandart(Grid):
    no_images_text = "Папка пуста или нет подключения к диску"

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

    def paste_files_fin(self, urls):
        urls = super().paste_files_fin(urls)
        self.force_load_images_cmd(urls)

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

        if not self.base_items:
            no_images = QLabel(GridStandart.no_images_text)
            no_images.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.addWidget(no_images, 0, 0)
            self.loading_lbl.hide()
            return

        # создаем иконки на основе расширений, если не было
        exts = {i.type_ for i in self.base_items}
        for ext in exts:
            icon_path = Utils.get_generic_icon_path(ext)
            if icon_path not in Dynamic.generic_icon_paths:
                path_to_svg = Utils.create_generic_icon(ext, icon_path)
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

        if self.main_win_item.go_to in self.url_to_wid:
            wid = self.url_to_wid.get(self.main_win_item.go_to)
            self.main_win_item.go_to = None
            self.select_one_wid(wid)

        elif self.main_win_item.urls:
            for i in self.main_win_item.urls:
                if i in self.url_to_wid:
                    wid = self.url_to_wid.get(i)
                    self.selected_widgets.append(wid)
                    wid.set_frame()
            self.main_win_item.urls.clear()

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
                Utils.print_error(e)

    def set_urls(self):
        """
        Из-за того, что сетка удаляется из MainWin по таймеру,
        нужно вызывать этот метод, чтобы .urls моментально обновились
        для обработки в следующей сетке
        """
        self.main_win_item.urls.clear()
        self.main_win_item.urls = [
            i.src
            for i in self.selected_widgets
        ]

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