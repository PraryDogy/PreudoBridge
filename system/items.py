
import os
import re
from multiprocessing import Queue
from typing import Literal

import numpy as np
import sqlalchemy
from PyQt5.QtGui import QImage

from cfg import Static
from system.shared_utils import ImgUtils

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
        self.qimages: dict[Literal["src"] | int, QImage] = {}
        self.img_array: np.ndarray = None

    def set_partial_hash(self):
        try:
            self.partial_hash = Utils.get_partial_hash(self.src)
            if self.type_ in ImgUtils.ext_all:
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


class ClipboardItem:
    src_urls: list[str] = []
    is_cut: bool = False
    is_search: bool = False
    src_dir: str = ""
    dst_dir: str = ""

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
        ClipboardItem.src_urls = []
        ClipboardItem.is_cut = False
        ClipboardItem.is_search = False
        ClipboardItem.src_dir = ""
        ClipboardItem.dst_dir = ""


class DirItem:
    def __init__(self, _main_win_item: MainWinItem, _sort_item: SortItem, _show_hidden: bool):
        super().__init__()
        self.data_items: list[DataItem] = []
        self._main_win_item = _main_win_item
        self._sort_item = _sort_item
        self._show_hidden = _show_hidden


class JpgConvertItem:
    def __init__(self, _urls: list[str]):
        super().__init__()
        self.current_count: int
        self.current_filename: str
        self.msg: Literal["", "finished"]
        self._urls = _urls


class MultipleInfoItem:
    def __init__(self):
        super().__init__()
        self.total_size = 0
        self.total_files = 0
        self.total_folders = 0
        self._folders_set = set()
        self._files_set = set()


class SearchItem:
    def __init__(self):
        super().__init__()
        self.search_list: list[str] = []
        self.search_list_low: list[str] = []

        self.root_dir: str
        self.conn: sqlalchemy.Connection
        self.proc_q: Queue
        self.gui_q: Queue


class CopyItem:
    def __init__(self, src_dir: str, dst_dir: str, src_urls: list[str], is_search: bool, is_cut: bool):
        super().__init__()
        self.src_dir = src_dir
        self.dst_dir = dst_dir
        self.src_urls = src_urls
        self.is_search = is_search
        self.is_cut = is_cut

        self.current_size: int = 0
        self.total_size: int = 0
        self.current_count: int = 0
        self.total_count: int = 0
        self.dst_urls: list[str] = []
        self.msg: Literal["", "error", "need_replace", "replace_one", "replace_all", "finished"]