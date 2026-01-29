
import os
import re
from pathlib import Path
from typing import Literal

import sqlalchemy
from PyQt5.QtGui import QImage

from cfg import Static

from .database import CACHE, Clmns
from .utils import Utils


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


class DataItem:
    def __init__(self, src: str, rating: int = 0):
        super().__init__()
        self.src: str = src
        self.filename: str = None
        self.type_: str = None
        self.rating: int = rating
        self.mod: float = None
        self.birth: int = None
        self.size: int = None
        self.uti_type: str = None
        self.partial_hash: str = None
        self.thumb_path: str = None
        self.image_is_loaded: bool = False
        self.must_hidden: bool = False
        self.row, self.col = 0, 0

        # {"src": QImage(), 100: Qimage(), 200: QImage, ...}
        # словарь заполняется на основе Static.image_sizes
        # так же дополняется ключом "src" с исходным qimage
        self.qimages: dict = None
        self.img_array: dict = None

    def set_partial_hash(self):
        try:
            self.partial_hash = Utils.get_partial_hash(self.src)
            if self.type_ in Static.img_exts:
                thumb_path = Utils.get_abs_thumb_path(self.partial_hash)
                if self.type_ in (".png", ".icns"):
                    self.thumb_path = thumb_path + ".png"
                else:
                    self.thumb_path = thumb_path + ".jpg"
        except Exception as e:
            print("items, BaseItem set partial hash error", e)
        
    def set_properties(self):
        """
        Обновляет данные объекта:
        src, filename, type_, mod, birth, size, rating
        """
        self.src = self.src.rstrip(os.sep)
        self.filename = os.path.basename(self.src)

        if os.path.isdir(self.src):
            self.type_ = Static.folder_type
        else:
            _, self.type_ = os.path.splitext(self.src)

        # _, ext = os.path.splitext(self.src)
        # self.type_ = ext if ext else Static.folder_type

        try:
            stat = os.stat(self.src)
            self.mod = int(stat.st_mtime)
            self.birth = int(stat.st_birthtime)
            self.size = int(stat.st_size)

        except Exception as e:
            print("items, BaseItem set properties error", e)
            self.mod = 0
            self.birth = 0
            self.size = 0

    @classmethod
    def sort_(cls, data_items: list["DataItem"], sort_item: SortItem) -> list["DataItem"]:

        def get_nums(filename: str):
            """
            Извлекает начальные числа из имени data_item для числовой сортировки.
            Например: "123 Te99st33" → 123
            """
            return int(re.match(r'^\d+', filename).group())
        
        if sort_item.get_sort_type() == sort_item.filename:
            num_data_items: list[DataItem] = []
            abc_data_items: list[DataItem] = []
            for i in data_items:
                if i.filename[0].isdigit():
                    num_data_items.append(i)
                else:
                    abc_data_items.append(i)
            key_num = lambda data_item: get_nums(data_item.filename)
            key_abc = lambda data_item: getattr(data_item, sort_item.get_sort_type())
            num_data_items.sort(key=key_num, reverse=sort_item.get_reversed())
            abc_data_items.sort(key=key_abc, reverse=sort_item.get_reversed())
            return [*num_data_items, *abc_data_items]
        else:
            key = lambda data_otem: getattr(data_otem, sort_item.get_sort_type())
            data_items.sort(key=key, reverse=sort_item.get_reversed())
            return data_items
        
    @classmethod
    def get_folder_conds(cls, data_item: "DataItem"):
        """
        Возвращает условия для поиска папки в базе данных
        """
        conds = [
            Clmns.name == data_item.filename,
            Clmns.type == data_item.type_,
            Clmns.size == data_item.size,
            Clmns.birth == data_item.birth,
            Clmns.mod == data_item.mod,
        ]
        return sqlalchemy.and_(*conds)

    @classmethod
    def update_folder_stmt(cls, data_item: "DataItem"):
        """
        Обновляет last_read
        """
        stmt = sqlalchemy.update(CACHE)
        stmt = stmt.where(*DataItem.get_folder_conds(data_item))
        stmt = stmt.values(**{
            Clmns.last_read.name: Utils.get_now()
        })
        return stmt
    
    @classmethod
    def update_file_stmt(cls, data_item: "DataItem"):
        """
        Обновляет last_read
        """
        stmt = sqlalchemy.update(CACHE)
        stmt = stmt.where(
            Clmns.partial_hash == data_item.partial_hash
        )
        stmt = stmt.values(**{
            Clmns.last_read.name: Utils.get_now()
        })
        return stmt
    
    @classmethod
    def insert_folder_stmt(cls, data_item: "DataItem"):
        stmt = sqlalchemy.insert(CACHE)
        stmt = stmt.values(**{
            Clmns.name.name: data_item.filename,
            Clmns.type.name: data_item.type_,
            Clmns.size.name: data_item.size,
            Clmns.birth.name: data_item.birth,
            Clmns.mod.name: data_item.mod,
            Clmns.last_read.name: Utils.get_now(),
            Clmns.rating.name: 0,
        })
        return stmt
    
    @classmethod
    def insert_file_stmt(cls, data_item: "DataItem"):
        stmt = sqlalchemy.insert(CACHE)
        stmt = stmt.values(**{
            Clmns.name.name: data_item.filename,
            Clmns.type.name: data_item.type_,
            Clmns.size.name: data_item.size,
            Clmns.birth.name: data_item.birth,
            Clmns.mod.name: data_item.mod,
            Clmns.last_read.name: Utils.get_now(),
            Clmns.rating.name: 0,
            Clmns.partial_hash.name: data_item.partial_hash,
            Clmns.thumb_path.name: data_item.thumb_path
        })
        return stmt


class SearchItem:
    SEARCH_LIST_TEXT = "Найти по списку"
    SEARCH_EXTENSIONS = {
        "Найти jpg": Static.jpg_exts,
        "Найти png": Static.png_exts,
        "Найти tiff": Static.tiff_exts,
        "Найти psd/psb": Static.psd_exts,
        "Найти raw": Static.raw_exts,
        "Найти видео": Static.movie_exts,
        "Найти любые фото": Static.img_exts
    }

    def __init__(self):
        super().__init__()
        self._filter: int = 0
        self._content: str | list[str] = None
        self.set_filter(2)

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
        self.exists: bool = True

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
    is_cut: bool = False
    is_search: bool = False
    src_dir: str = ""
    dst_dir: str = ""

    total_size: int = 0
    current_size: int = 0
    total_count: int = 0
    current_count: int = 0
    system_msg: Literal["error", "cancel", "single", "all"] = ""


    @classmethod
    def set_src(cls, src: str):
        cls.src_dir = src

    @classmethod
    def get_src(cls):
        return cls.src_dir
    
    @classmethod
    def set_is_cut(cls, value: bool):
        cls.is_cut = value

    @classmethod
    def get_is_cut(cls):
        return cls.is_cut
    
    @classmethod
    def set_dest(cls, dest: str):
        cls.dst_dir = dest

    @classmethod
    def get_dest(cls):
        return cls.dst_dir
    
    @classmethod
    def set_is_search(cls, value: bool):
        cls.is_search = value

    @classmethod
    def get_is_search(cls):
        return cls.is_search

    @classmethod
    def reset(cls):
        CopyItem.urls: list[str] = []
        CopyItem.is_cut: bool = False
        CopyItem.is_search: bool = False
        CopyItem.src_dir: str = ""
        CopyItem.dst_dir: str = ""

        CopyItem.total_size: int = 0
        CopyItem.current_size: int = 0
        CopyItem.total_count: int = 0
        CopyItem.current_count: int = 0
        CopyItem.system_msg: Literal["error", "cancel", "single", "all"] = ""