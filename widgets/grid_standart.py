import gc
import os
import weakref

import numpy as np
from PyQt5.QtCore import QObject, QRunnable, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QLabel, QWidget
from sqlalchemy import Connection, insert, select, update

from cfg import Dynamic, Static, ThumbData
from database import CACHE, ColumnNames, Dbase
from fit_img import FitImg
from utils import UThreadPool, Utils

from ._base_items import BaseItem
from .finder_items import FinderItems, LoadingWid
from .grid import Grid, Thumb


class AnyBaseItem:
    """
    QRunnable
    """

    @classmethod
    def check_db_record(cls, conn: Connection, thumb: Thumb) -> None:
        """
        Проверяет, есть ли запись в базе данных об этом Thumb по имени.    
        Если записи нет, делает запись.
        Thumb: любой файл, кроме файлов изображений и папок.
        """
        if not cls.load_db_record(conn, thumb):
            cls.insert_new_record(conn, thumb)

    @classmethod
    def load_db_record(cls, conn: Connection, thumb: Thumb):
        """
        Загружает id записи (столбец не принципиален) с условием по имени.  
        Возвращает True если запись есть, иначе False.
        """
        stmt = select(CACHE.c.id)
        stmt = stmt.where(CACHE.c.name == Utils.get_hash_filename(thumb.name))
        res_by_src = Dbase.execute_(conn, stmt).mappings().first()
        if res_by_src:
            return True
        else:
            return False

    @classmethod
    def insert_new_record(cls, conn: Connection, thumb: Thumb):
        """
        Новая запись в базу данных.
        """
        new_name = Utils.get_hash_filename(filename=thumb.name)

        values = {
            ColumnNames.NAME: new_name,
            ColumnNames.TYPE: thumb.type_,
            ColumnNames.RATING: 0,
        }

        q = insert(CACHE).values(**values)
        Dbase.commit_(conn, q)


class ImageBaseItem:
    """
    QRunnable
    """

    @classmethod
    def get_pixmap(cls, conn: Connection, thumb: Thumb) -> QPixmap:
        """
        Возвращает QPixmap либо из базы данных, либо созданный из изображения.
        """
        img_array = cls.get_img_array(conn, thumb)
        return Utils.pixmap_from_array(img_array)

    @classmethod
    def get_img_array(cls, conn: Connection, thumb: Thumb) -> np.ndarray:
        """
        Загружает данные о Thumb из базы данных. Возвращает np.ndarray
        """

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
        res_by_name = Dbase.execute_(conn, stmt).mappings().first()

        if res_by_name:
            if res_by_name.get(ColumnNames.MOD) != int(thumb.mod):
                # print("даты не совпадают", res_by_name.get(ColumnNames.MOD), thumb.mod)
                return cls.update_db_record(conn, thumb, res_by_name.get(ColumnNames.ID))
            else:
                # print("ok", thumb.src)
                return Utils.bytes_to_array(res_by_name.get(ColumnNames.IMG))
        else:
            # print("new_record", thumb.src)
            return cls.insert_db_record(conn, thumb)
    
    @classmethod
    def update_db_record(cls, conn: Connection, thumb: Thumb, row_id: int) -> np.ndarray:
        """
        Обновляет запись в базе данных:     
        имя, изображение bytes, размер, дата изменения, разрешение, хеш 10мб
        """
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
        q = update(CACHE).where(CACHE.c.id == row_id)
        q = q.values(**values)
        Dbase.commit_(conn, q)
        return img_array

    @classmethod
    def insert_db_record(cls, conn: Connection, thumb: Thumb) -> np.ndarray:
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
        q = insert(CACHE).values(**values)
        Dbase.commit_(conn, q)
        return img_array
    
    @classmethod
    def get_small_ndarray_img(cls, src: str) -> np.ndarray:
        img_array_src = Utils.read_image(src)
        img_array = FitImg.start(img_array_src, ThumbData.DB_IMAGE_SIZE)
        img_array_src = None
        del img_array_src
        return img_array
    
    @classmethod
    def get_stats(cls, src: str, img_array: np.ndarray):
        """
        Возвращает: размер, дату изменения, разрешение
        """
        stats = os.stat(src)
        height, width = img_array.shape[:2]
        new_size = int(stats.st_size)
        new_mod = int(stats.st_mtime)
        new_resol = f"{width}x{height}"
        return new_size, new_mod, new_resol


class WorkerSignals(QObject):
    update_thumb = pyqtSignal(Thumb)
    finished_ = pyqtSignal()


class LoadImages(QRunnable):
    def __init__(self, main_dir: str, thumbs: list[Thumb], parent: QWidget):
        """
        QRunnable   
        Сортирует список Thumb по размеру по возрастанию для ускорения загрузки
        Загружает изображения из базы данных или создает новые
        """
        super().__init__()
        self.signals_ = WorkerSignals()
        self.main_dir = main_dir
        self.parent_ref = weakref.ref(parent)
        self.thumbs = thumbs
        key_ = lambda x: x.size
        self.thumbs.sort(key=key_)

    def run(self):
        """
        Создает подключение к базе данных   
        Запускает обход списка Thumb для загрузки изображений   
        Испускает сигнал finished_
        """
        if not self.thumbs:
            return

        db = os.path.join(self.main_dir, Static.DB_FILENAME)
        self.dbase = Dbase()
        engine = self.dbase.create_engine(path=db)

        if engine is None:
            return

        self.conn = engine.connect()
        self.process_thumbs()
        self.conn.close()

        try:
            self.signals_.finished_.emit()
        except RuntimeError:
            ...

    def process_thumbs(self):
        """
        Обходит циклом список Thumb     
        Пытается загрузить изображение из базы данных или создает новое,
        чтобы передать его в Thumb
        """
        for thumb in self.thumbs:

            if not self.parent_ref():
                return
                        
            try:
                if thumb.type_ not in Static.ext_all:
                    AnyBaseItem.check_db_record(self.conn, thumb)
                else:
                    pixmap = ImageBaseItem.get_pixmap(self.conn, thumb)
                    thumb.set_pixmap_storage(pixmap)
                    self.signals_.update_thumb.emit(thumb)
            except RuntimeError:
                return

            except Exception as e:
                continue


class GridStandart(Grid):
    no_images_text = "Папка пуста или нет подключения к диску"
    limit: int = 50

    def __init__(self, main_dir: str, view_index: int, url_for_select: str):
        """
        Стандартная сетка виджетов.

        Параметры:
        - main_dir: Основная директория, содержимое которой будет отображено в виде сетки (Thumb).
        - view_index: Режим отображения. 
            0 — сетка, 
            1 — список. 
            Значение передаётся в родительский виджет для корректной работы, например, в actions.py > ChangeViewMenu.
        - url_for_select: Путь к файлу или папке, который должен быть выделен после загрузки содержимого.
            Например: 
            main_dir — папка "Загрузки", 
            url_for_select — "изображение 1.jpg". 
            После загрузки виджет, соответствующий пути "Загрузки/изображение 1.jpg", будет найден и выделен.
        """
        super().__init__(main_dir, view_index, url_for_select)

        # список url для предотвращения повторной загрузки изображений
        self.loaded_images: list[str] = []

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

        # QRunnable FinderItems вернет все элементы из заданной директории
        # где base items это существующие в базе данных записи по элементам
        # а new_items - элементы, записей по которым нет в базе данных
        self.base_items: list[BaseItem] = []
        self.new_items: list[BaseItem] = []

    def load_visible_images(self):
        """
        Составляет список Thumb виджетов, которые находятся в зоне видимости.   
        Запускает загрузку изображений через QRunnable
        """
        visible_widgets: list[Thumb] = []
        for widget in self.main_wid.findChildren(Thumb):
            if not widget.visibleRegion().isEmpty():
                if widget.src not in self.loaded_images:
                    visible_widgets.append(widget)
        self.run_load_images_thread(visible_widgets)

    def force_load_images_cmd(self, urls: list[str]):
        """
        Находит виджеты Thumb по url.   
        Принудительно запускает загрузку изображений через QRunnable
        """
        thumbs: list[Thumb] = [
            self.url_to_wid.get(url)
            for url in urls
            if url in self.url_to_wid
        ]
        self.run_load_images_thread(thumbs)

    def on_scroll_changed(self, value: int):
        """
        - При сколлинге запускается таймер    
        - Запускается load visible images
        - Если скролл достиг низа, подгрузить следующие limit айтемов
        """
        self.load_images_timer.stop()
        self.load_images_timer.start(1000)

        if value == self.verticalScrollBar().maximum():
            self.iter_base_items()

    def load_finder_items(self):
        """
        QRunnable   
        Обходит заданную директорию os scandir.      
        Генерирует на основе содержимого директории список BaseItem.    
        Проверяет на наличие BaseItem в базе данных.          
        Загружает рейтинг BaseItem из базы данных, если имеется.     
        Испускает сигнал finished_, который содержит кортеж:
        - список всех BaseItem
        - список новых BaseItem, которых не было в базе данных
        """
        finder_thread = FinderItems(self.main_dir, self.sort_item, self)
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
        self.loading_lbl.hide()

        # испускаем сигнал в MainWin, чтобы нижний бар с отображением пути
        # обновился на актуальный путь
        self.path_bar_update.emit(self.main_dir)

        # высчитываем размер Thumb
        Thumb.calculate_size()

        if not self.base_items:
            no_images = QLabel(GridStandart.no_images_text)
            no_images.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.addWidget(no_images, 0, 0)
            return

        # создаем иконки на основе расширений, если не было
        exts = {i.type_ for i in self.base_items}
        for ext in exts:
            icon_path = Utils.get_generic_icon_path(ext)
            if icon_path not in Dynamic.generic_icon_paths:
                path_to_svg = Utils.create_generic_icon(ext)
                Dynamic.generic_icon_paths.append(path_to_svg)

        # создаем сетку на основе элементов из FinderItems с лимитом
        self.iter_base_items()

        # испускаем сигнал в MainWin для обновления нижнего бара
        # для отображения "всего элементов"
        self.sort_bar_update.emit(len(self.base_items))

        # если установлен фильтр по рейтингу, запускаем функцию фильтрации,
        # которая скроет из сетки не подходящие под фильтр виджеты
        if Dynamic.rating_filter > 0:
            self.filter_()

        # если не будет прокрутки, то начнется подгрузка изображений в виджеты
        # в видимой области
        self.load_images_timer.start(100)

    def iter_base_items(self):
        self.col_count = self.get_col_count()
        for base_item in self.base_items[:GridStandart.limit]:
            thumb = Thumb(base_item.src, base_item.rating)
            thumb.setup_attrs()
            thumb.setup_child_widgets()
            thumb.set_no_frame()

            # если путь состоит только из 2 секций: /Volumes/Macintosh HD
            # то это точно диск, устанавливаем соответствующую иконку
            if base_item.src.count(os.sep) == 2:
                thumb.set_svg_icon(Static.HDD_SVG)

            # иконка на основе расширения файла для виджета уже точно есть
            # проверка была в finalize finder items
            else:
                icon_path = Utils.get_generic_icon_path(base_item.type_)
                thumb.set_svg_icon(icon_path)
            
            if base_item in self.new_items:
                thumb.set_green_text()

            # удаляем элемент из списка base items
            # таким образом в следующем обращении к iter base items
            # список base items будет актуальным
            self.base_items.remove(base_item)

            self.add_widget_data(thumb, self.row, self.col)
            self.grid_layout.addWidget(thumb, self.row, self.col)

            # обновляем данные сетки, чтобы следующие iter base items
            # так же знали актуальные данные сеткик
            self.col += 1
            if self.col >= self.col_count:
                self.col = 0
                self.row += 1

    def run_load_images_thread(self, thumbs: list[Thumb]):
        """
        QRunnable   
        Запускает загрузку изображений для списка Thumb.    
        Изоражения загружаются из базы данных или берутся из заданной
        директории, если их нет в базе данных.
        """
        # передаем виджеты Thumb из сетки изображений в зоне видимости
        # в QRunnable для подгрузки изображений
        # в самом QRunnable нет обращений напрямую к Thumb
        # а только испускается сигнал
        thread_ = LoadImages(self.main_dir, thumbs, self)
        thread_.signals_.update_thumb.connect(lambda thumb: self.set_thumb_image(thumb))
        UThreadPool.start(thread_)
    
    def set_thumb_image(self, thumb: Thumb):
        """
        Получает QPixmap из хранилища Thumb.    
        Устанавливает QPixmap в Thumb для отображения в сетке.
        """
        try:
            pixmap = thumb.get_pixmap_storage()
            if thumb in self.sorted_widgets and pixmap:
                thumb.set_image(pixmap)
                self.loaded_images.append(thumb.src)
        except RuntimeError:
            ...

    def resizeEvent(self, a0):
        self.loading_lbl.center(self)
        return super().resizeEvent(a0)
