import gc
import os
import re

import numpy as np
import sqlalchemy
from PyQt5.QtGui import QImage, QPixmap
from sqlalchemy.engine import RowMapping

from cfg import Static, ThumbData
from system.shared_utils import ReadImage, SharedUtils

from .database import CACHE, Clmns, Dbase
from .utils import Utils
from datetime import datetime

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

        self.partial_hash: str = None
        self.thumb_path: str = None

    def set_properties(self):
        """
        Обновляет данные объекта:
        src, filename, type_, mod, birth, size, rating
        """
        self.src = self.src.rstrip(os.sep)
        self.filename = os.path.basename(self.src)

        if os.path.isdir(self.src):
            self.type_ = Static.FOLDER_TYPE
        else:
            _, self.type_ = os.path.splitext(self.src)

        try:
            stat = os.stat(self.src)
            self.mod = int(stat.st_mtime)
            self.birth = int(stat.st_birthtime)
            self.size = int(stat.st_size)
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
        
    @classmethod
    def folder_conditions(cls, base_item: "BaseItem"):
        """
        Возвращает условия для поиска папки в базе данных
        """
        conds = [
            Clmns.name == base_item.filename,
            Clmns.type == base_item.type_,
            Clmns.size == base_item.size,
            Clmns.birth == base_item.birth,
            Clmns.mod == base_item.mod,
        ]
        return sqlalchemy.and_(*conds)


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
