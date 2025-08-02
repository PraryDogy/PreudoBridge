import os
import re

import numpy as np
from PyQt5.QtGui import QPixmap
from sqlalchemy import (Connection, Insert, Row, RowMapping, Update, insert,
                        select, update)
from sqlalchemy.engine import RowMapping

from cfg import Static, ThumbData
from evlosh_templates.evlosh_utils import EvloshUtils
from evlosh_templates.fit_image import FitImage
from evlosh_templates.read_image import ReadImage

from .database import CACHE, ColumnNames, Dbase
from .utils import ImageUtils, Utils


class SortItem:
    filename = "filename"
    type_ = "type_"
    size = "size"
    mod = "mod"
    birth = "birth"
    rating = "rating"

    lang_dict: dict[str, str] = {
        filename : "Имя",
        type_ : "Тип",
        size : "Размер",
        mod : "Дата изменения",
        birth: "Дата создания",
        rating : "Рейтинг",
    }

    def __init__(self):
        super().__init__()
        self._sort_type: str = self.filename
        self._reversed: bool = False

    def get_attrs(self):
        return list(self.lang_dict.keys())

    def set_reversed(self, value: bool):
        self._reversed = value
        
    def get_reversed(self):
        return self._reversed

    def set_sort_type(self, value: str):
        self._sort_type = value
        
    def get_sort_type(self):
        return self._sort_type


class BaseItem:
    def __init__(self, src: str, rating: int = 0):
        """
        Вызовите setup_attrs после инициации экземпляра класса.     

        Базовый виджет, предшественник grid.py > Thumb.
        Используется для передачи данных между потоками и функциями.

        Пример использования:
        - В дополнительном потоке создаётся экземпляр класса BaseItem
        - Экземпляру присваивается имя "TEST" через атрибут name.
        - Этот экземпляр передаётся в основной поток через сигнал.
        - В основном потоке создаётся экземпляр класса Thumb (из модуля grid.py).
        - Атрибут name у Thumb устанавливается на основе значения BaseItem.name ("TEST").

        В BaseItem обязаны присутствовать все аттрибуты, соответствующие Sort.items
        """
        super().__init__()
        self.src: str = src
        self.filename: str = None
        self.type_: str = None
        self.rating: int = rating
        self.mod: int = None
        self.birth: int = None
        self.size: int = None
        self.pixmap_storage: QPixmap = None

    def set_pixmap_storage(self, pixmap: QPixmap):
        """
        Сохраняет QPixmap, переданный, например, из дополнительного потока в основной.
        """
        self.pixmap_storage = pixmap

    def get_pixmap_storage(self):
        """
        Возвращает ранее сохранённый QPixmap.
        """
        return self.pixmap_storage

    def setup_attrs(self):
        """
        Устанавливает параметры: src, name, type, mod, birth, size, rating
        """
        self.src = EvloshUtils.normalize_slash(self.src)
        self.filename = os.path.basename(self.src)

        if os.path.isdir(self.src):
            self.type_ = Static.FOLDER_TYPE
        else:
            _, self.type_ = os.path.splitext(self.src)

        try:
            stat = os.stat(self.src)
            self.mod = stat.st_mtime
            self.birth = stat.st_birthtime
            self.size = stat.st_size
        except Exception as e:
            Utils.print_error()
            self.mod = 0
            self.birth = 0
            self.size = 0
        # Поправка старой системы рейтинга, когда рейтинг был двузначным
        self.rating = self.rating % 10

    @staticmethod
    def check_sortitem_attrs():
        sort_attrs = SortItem().get_attrs()
        base_item = BaseItem("__dummy__")
        missing = [attr for attr in sort_attrs if not hasattr(base_item, attr)]
        if missing:
            raise AttributeError(f"В Thumb отсутствуют атрибуты сортировки: {missing}")

    @classmethod
    def sort_(cls, base_items: list["BaseItem"], sort_item: SortItem) -> list["BaseItem"]:

        def get_nums(filename: str):
            """
            Извлекает начальные числа из имени base_item для числовой сортировки.
            Например: "123 Te99st33" → 123
            """
            return int(re.match(r'^\d+', filename).group())
        
        attr = sort_item.get_sort_type()
        rev = sort_item.get_reversed()
        if attr == sort_item.filename:
            num_base_items: list[BaseItem] = []
            abc_base_items: list[BaseItem] = []
            for i in base_items:
                if i.filename[0].isdigit():
                    num_base_items.append(i)
                else:
                    abc_base_items.append(i)
            key_num = lambda base_item: get_nums(base_item.filename)
            key_abc = lambda base_item: getattr(base_item, attr)
            num_base_items.sort(key=key_num, reverse=rev)
            abc_base_items.sort(key=key_abc, reverse=rev)
            return [*num_base_items, *abc_base_items]
        else:
            key = lambda base_item: getattr(base_item, attr)
            base_items.sort(key=key, reverse=rev)
            return base_items


class SearchItem:
    SEARCH_LIST_TEXT = "Найти по списку"
    SEARCH_EXTENSIONS = {
        "Найти jpg": Static.ext_jpeg,
        "Найти png": Static.ext_png,
        "Найти tiff": Static.ext_tiff,
        "Найти psd/psb": Static.ext_psd,
        "Найти raw": Static.ext_raw,
        "Найти видео": Static.ext_video,
        "Найти любые фото": Static.ext_all
    }

    def __init__(self):
        super().__init__()
        self._filter: int = 0
        self._content: str | list[str] = None

    def get_content(self):
        """
        none    
        str: искать текст   
        tuple[str]: искать по расширениям   
        list[str]: искать по списку 
        """
        return self._content

    def set_content(self, value: str | tuple[str] | list[str]):
        """
        none    
        str: искать текст   
        tuple: искать по расширениям    
        list[str]: искать по списку     
        """
        self._content = value
    
    def set_filter(self, value: int):
        """
        0: нет фильтра      
        1: точное соответствие  
        2: искомый текст содержится в имени и наоборот  
        """
        self._filter = value

    def get_filter(self):
        """
        0: нет фильтра  
        1: точное соответствие  
        2: искомый текст содержится в имени и наоборот  
        """
        return self._filter
    
    def reset(self):
        self.set_content(None)
        self.set_filter(0)


class MainWinItem:
    def __init__(self):
        self._urls: list[str] = []
        self._go_to: str = None
        self.main_dir: str = None
        self.scroll_value: int = None
        self.view_mode: int = 0

    def set_view_mode(self, value: int):
        self.view_mode = value

    def get_view_mode(self):
        """
        0 вид сетка, 1 вид список
        """
        return self.view_mode

    def set_urls(self, urls: list[str]):
        self._urls = urls

    def get_urls(self):
        return self._urls

    def set_go_to(self, path: str):
        self._go_to = path

    def get_go_to(self):
        return self._go_to
    
    def clear_urls(self):
        self._urls.clear()

    def clear_go_to(self):
        self._go_to = None


class AnyBaseItem:
    def __init__(self, conn: Connection, base_item: BaseItem):
        super().__init__()
        self.conn = conn
        self.base_item = base_item

    def get_stmt(self) -> Insert | None:
        if not self._check_db_record():
            return self._get_insert_stmt()
        else:
            return None

    def _check_db_record(self):
        stmt = select(CACHE.c.id)
        stmt = stmt.where(CACHE.c.name == Utils.get_hash_filename(self.base_item.filename))
        if Dbase.execute_(self.conn, stmt).first():
            return True
        return None

    def _get_insert_stmt(self) -> Insert | None:
        hash_filename = Utils.get_hash_filename(self.base_item.filename)
        values = {
            ColumnNames.NAME: hash_filename,
            ColumnNames.TYPE: self.base_item.type_,
            ColumnNames.RATING: 0,
        }
        return insert(CACHE).values(**values)


class ImageBaseItem:
    update_flag = "_update"
    insert_flag = "_insert"
    already_flag = "_already"
    none_text = "None"

    def __init__(self, conn: Connection, base_item: BaseItem):
        super().__init__()
        self.conn = conn
        self.base_item = base_item

    def get_stmt_pixmap(self) -> tuple[Insert | Update | None, QPixmap | None]:
        result = self._check_db_record()

        if self.update_flag in result:
            row = result[self.update_flag]
            img_array = self._get_small_ndarray_img()
            stmt = self._get_update_stmt(row, img_array)

        elif self.insert_flag in result:
            img_array = self._get_small_ndarray_img()
            stmt = self._get_insert_stmt(img_array)

        elif self.already_flag in result:
            row = result[self.already_flag]
            bytes_img = row.get(ColumnNames.IMG)
            img_array = ImageUtils.bytes_to_array(bytes_img)
            stmt = None
        
        pixmap = ImageUtils.pixmap_from_array(img_array)
        pixmap = ImageUtils.pixmap_scale(pixmap, ThumbData.DB_IMAGE_SIZE)

        return (stmt, pixmap)

    def _check_db_record(self) -> dict[str, RowMapping | None]:
        stmt = select(
            CACHE.c.id,
            CACHE.c.img,
            CACHE.c.size,
            CACHE.c.mod,
            CACHE.c.rating
        )

        stmt = stmt.where(
            CACHE.c.name == Utils.get_hash_filename(self.base_item.filename)
        )
        row = Dbase.execute_(self.conn, stmt).mappings().first()

        if row:
            if row.get(ColumnNames.MOD) != int(self.base_item.mod):
                return {self.update_flag: row}
            else:
                return {self.already_flag: row}
        else:
            return {self.insert_flag: None}

    def _get_update_stmt(self, row: RowMapping, img_array: np.ndarray) -> Update | None:
        new_bytes_img = ImageUtils.numpy_to_bytes(img_array)
        hash_filename = Utils.get_hash_filename(self.base_item.filename)
        stats = self._get_stats()
        if new_bytes_img and stats:
            values = {
                ColumnNames.NAME: hash_filename,
                ColumnNames.IMG: new_bytes_img,
                ColumnNames.SIZE: int(self.base_item.size),
                ColumnNames.MOD: int(self.base_item.mod),
            }
            stmt = update(CACHE).where(CACHE.c.id == row.get(ColumnNames.ID))
            stmt = stmt.values(**values)
            return stmt
        else:
            return None

    def _get_insert_stmt(self, img_array: np.ndarray) -> Update | None:
        new_bytes_img = ImageUtils.numpy_to_bytes(img_array)
        hash_filename = Utils.get_hash_filename(self.base_item.filename)
        stats = self._get_stats()
        if new_bytes_img and stats:
            values = {
                ColumnNames.IMG: new_bytes_img,
                ColumnNames.NAME: hash_filename,
                ColumnNames.TYPE: self.base_item.type_,
                ColumnNames.SIZE: int(self.base_item.size),
                ColumnNames.MOD: int(self.base_item.mod),
                ColumnNames.RATING: 0,
                ColumnNames.RESOL: self.none_text,
                ColumnNames.CATALOG: self.none_text,
                ColumnNames.PARTIAL_HASH: self.none_text
            }
            stmt = insert(CACHE)
            stmt = stmt.values(**values)
            return stmt
        else:
            return None
    
    def _get_small_ndarray_img(self) -> np.ndarray:
        img_array = ReadImage.read_image(self.base_item.src)
        return FitImage.start(img_array, ThumbData.DB_IMAGE_SIZE)
    
    def _get_stats(self) -> os.stat_result:
        try:
            return os.stat(self.base_item.src)
        except Exception as e:
            Utils.print_error()
            return None