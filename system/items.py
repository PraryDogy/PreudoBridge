
import os
import re
from dataclasses import dataclass
from multiprocessing import Queue
from typing import Literal

import numpy as np
import sqlalchemy
from PyQt5.QtGui import QImage

from cfg import Static
from system.shared_utils import ImgUtils

from .database import CacheTable
from .utils import Utils


class SortItem:
    filename = "filename"
    type_ = "type_"
    size = "size"
    mod = "mod"
    birth = "birth"

    attr_lang = {
        filename : "Имя",
        type_ : "Тип",
        size : "Размер",
        mod : "Дата изменения",
        birth: "Дата создания"
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
    def __init__(self, src: str):
        super().__init__()
        self.abs_path: str = src

        # устанавливается через set_properties
        self.filename: str
        self.type_: str
        self.mod: int
        self.size: int

        # в процессе работы и gui
        self.must_hidden: bool = False
        self.row, self.col = 0, 0
        # {"src": QImage(), 100: Qimage(), 200: QImage, ...}
        # словарь заполняется на основе Static.image_sizes
        # так же дополняется ключом "src" с исходным qimage
        self.qimages: dict[Literal["src"] | int, QImage] = {}

        # нужно чтоб перекинуть с мультипроцесса в основной поток 
        self._img_array: np.ndarray = None
        # для внутренней работы ImgLoader, SearchTask в multiprocess
        self._thumb_path: str

    def set_properties(self):
        self.abs_path = self.abs_path.rstrip(os.sep)
        self.filename = os.path.basename(self.abs_path)

        if os.path.isdir(self.abs_path):
            self.type_ = Static.folder_type
        else:
            _, self.type_ = os.path.splitext(self.abs_path)

        try:
            stat = os.stat(self.abs_path)
            self.mod = int(stat.st_mtime)
            self.size = int(stat.st_size)
        except Exception as e:
            print("items, BaseItem set properties error", e)
            self.mod = 0
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
            CacheTable.name == data_item.filename,
            CacheTable.type == data_item.type_,
            CacheTable.size == data_item.size,
            CacheTable.birth == data_item.birth,
            CacheTable.mod == data_item.mod,
        ]
        return sqlalchemy.and_(*conds)
            

class MainWinItem:
    def __init__(self):
        self.urls_to_select: list[str]
        self.go_to: str
        self.abs_current_dir: str
        self.view_mode: int 
        self.fs_id: str
        self.rel_parent: str

    def set_view_mode(self, value: int):
        self.view_mode = value

    def get_view_mode(self):
        """
        0 вид сетка, 1 вид список
        """
        return self.view_mode
    
    def set_current_dir(self, path: str):
        self.abs_current_dir = path
        self.fs_id = Utils.get_fs_id(path)
        self.rel_parent = Utils.get_rel_parent(path)


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
        self.fixed_path = ""


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

        # список для поиска:
        # айтем в нижнем регистре: оригинальный айтем
        self.search_list: dict[str, str] = {}
        # по мере поиска файлов, если файл найден, то он удаляется из
        # missed files, и в конце поиска в missed files останутся только
        # ненайденные файлы
        self.missed_files: dict[str, str] = {}

        self.root_dir: str
        self.queue: Queue
        self.engine: sqlalchemy.Engine

        # SINGLE DIR
        # эти данные нужны когда поиск сканирует директорию
        # данные динамически обновляются для новой директории
        # смотри system multiprocess SearchTask
        self.fs_id: str
        self.rel_parent: str
        self.db_items: dict
        self.new_items: list[DataItem] = []


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


class PathFixerItem:
    def __init__(self, fixed_path: str | None, is_dir: bool | None):
        super().__init__()
        self.fixed_path = fixed_path
        self.is_dir = is_dir


@dataclass(slots=True)
class ImgLoaderItem:
    engine: sqlalchemy.Engine
    queue: Queue
    fs_id: str
    rel_parent: str