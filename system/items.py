import gc
import os
import re

import numpy as np
from PyQt5.QtGui import QPixmap, QImage
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

    attr_lang = {
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
        return list(self.attr_lang.keys())

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
        Запустите set_properties, чтобы обновить данные.
        set_properties нельзя делать автозапуском, т.к. тогда Thumb, наследуемый
        от BaseItem, так же повторно будет запускать set_properties
        """
        super().__init__()
        self.src: str = src
        self.filename: str = None
        self.type_: str = None
        self.rating: int = rating
        self.mod: float = None
        self.birth: int = None
        self.size: int = None
        self.base_pixmap: QPixmap = None
        self.qimage: QImage = None

    def set_properties(self):
        """
        Обновляет данные объекта:
        src, filename, type_, mod, birth, size, rating
        """
        self.src = EvloshUtils.norm_slash(self.src)
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
        base_item = BaseItem("/Volumes")
        missing = [attr for attr in sort_attrs if not hasattr(base_item, attr)]
        if missing:
            raise AttributeError(f"\n\nВ Thumb отсутствуют атрибуты сортировки: {missing}\n\n")

    @classmethod
    def sort_items(cls, base_items: list["BaseItem"], sort_item: SortItem) -> list["BaseItem"]:

        def get_nums(filename: str):
            """
            Извлекает начальные числа из имени base_item для числовой сортировки.
            Например: "123 Te99st33" → 123
            """
            return int(re.match(r'^\d+', filename).group())
        
        if sort_item.get_sort_type() == sort_item.filename:
            num_base_items: list[BaseItem] = []
            abc_base_items: list[BaseItem] = []
            for i in base_items:
                if i.filename[0].isdigit():
                    num_base_items.append(i)
                else:
                    abc_base_items.append(i)
            key_num = lambda base_item: get_nums(base_item.filename)
            key_abc = lambda base_item: getattr(base_item, sort_item.get_sort_type())
            num_base_items.sort(key=key_num, reverse=sort_item.get_reversed())
            abc_base_items.sort(key=key_abc, reverse=sort_item.get_reversed())
            return [*num_base_items, *abc_base_items]
        else:
            key = lambda base_item: getattr(base_item, sort_item.get_sort_type())
            base_items.sort(key=key, reverse=sort_item.get_reversed())
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
        self.set_filter(1)

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
    

class MainWinItem:
    def __init__(self):
        self._urls_to_select: list[str] = []
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

    def set_urls_to_select(self, urls: list[str]):
        self._urls_to_select = urls

    def get_urls_to_select(self):
        return self._urls_to_select

    def clear_urls_to_select(self):
        self._urls_to_select = []

    def set_go_to(self, path: str):
        self._go_to = path

    def get_go_to(self):
        return self._go_to

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

    def get_stmt_qimage(self) -> tuple[Insert | Update | None, QImage | None]:
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
        
        if img_array is  None:
            qimage = None
        else:
            qimage = ImageUtils.qimage_from_array(img_array)

        return (stmt, qimage)

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
        try:
            row = Dbase.execute_(self.conn, stmt).mappings().first()
        except AttributeError:
            row = None

        if row:
            if row.get(ColumnNames.MOD) != int(self.base_item.mod):
                return {self.update_flag: row}
            else:
                return {self.already_flag: row}
        else:
            return {self.insert_flag: row}

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
        small_img = FitImage.start(img_array, ThumbData.DB_IMAGE_SIZE)
        del img_array
        gc.collect()
        return small_img
    
    def _get_stats(self) -> os.stat_result:
        try:
            return os.stat(self.base_item.src)
        except Exception as e:
            Utils.print_error()
            return None


class CopyItem:
    urls: list[str] = []
    _is_cut: bool = False
    _is_search: bool = False
    _src: str = None
    _dest: str = None

    @classmethod
    def set_src(cls, src: str):
        cls._src = src

    @classmethod
    def get_src(cls):
        return cls._src
    
    @classmethod
    def set_is_cut(cls, value: bool):
        cls._is_cut = value

    @classmethod
    def get_is_cut(cls):
        return cls._is_cut
    
    @classmethod
    def set_dest(cls, dest: str):
        cls._dest = dest

    @classmethod
    def get_dest(cls):
        return cls._dest
    
    @classmethod
    def set_is_search(cls, value: bool):
        cls._is_search = value

    @classmethod
    def get_is_search(cls):
        return cls._is_search

    @classmethod
    def reset(cls):
        cls.urls.clear()
        cls._is_cut = False
        cls._is_search = False
        cls._src = None
        cls._dest = None
