import os
import re
from dataclasses import dataclass
from multiprocessing import Queue
from typing import Literal

import numpy as np
import sqlalchemy
from PyQt5.QtGui import QImage

from cfg import Static

from .utils import Utils


@dataclass(slots=True)
class SortItem:
    filename = "filename"
    type_ = "type_"
    size = "size"
    mod = "mod"

    attr_lang = {
        filename : "Имя",
        type_ : "Тип",
        size : "Размер",
        mod : "Дата изменения"
    }

    item_type: str
    reversed: bool


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
        self.is_selected: bool = False
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
    def sort_(cls, data_items: list["DataItem"], sort_item: SortItem):

        def get_nums(filename: str):
            """
            Извлекает начальные числа из имени data_item для числовой сортировки.
            Например: "123 Te99st33" → 123
            """
            return int(re.match(r'^\d+', filename).group())
        
        if sort_item.item_type == sort_item.filename:
            num_data_items: list[DataItem] = []
            abc_data_items: list[DataItem] = []
            for i in data_items:
                if i.filename[0].isdigit():
                    num_data_items.append(i)
                else:
                    abc_data_items.append(i)
            key_num = lambda data_item: get_nums(data_item.filename)
            key_abc = lambda data_item: getattr(data_item, sort_item.item_type)
            num_data_items.sort(key=key_num, reverse=sort_item.reversed)
            abc_data_items.sort(key=key_abc, reverse=sort_item.reversed)
            return [*num_data_items, *abc_data_items]
        else:
            key = lambda data_otem: getattr(data_otem, sort_item.item_type)
            data_items.sort(key=key, reverse=sort_item.reversed)
            return data_items
        

class MainWinItem:
    def __init__(self):
        self.urls_to_select: list[str] = []
        self.go_to_widget: str = None
        self.abs_current_dir: str = None
        self.view_mode: int = 0
        self.fs_id: str = None
        self.rel_parent: str = None

    def set_view_mode(self, value: int):
        self.view_mode = value

    def get_view_mode(self):
        """
        0 вид сетка, 1 вид список
        """
        return self.view_mode
    
    def set_current_dir(self, path: str):
        if not os.path.exists(path):
            path = self.fix_path(path)
            if not os.path.exists(path):
                self.abs_current_dir = None
                self.fs_id = None
                self.rel_parent = None
                return None
        self.abs_current_dir = path
        self.fs_id = Utils.get_fs_id(path)
        self.rel_parent = Utils.get_rel_parent(path)
        return True

    def fix_path(self, path: str):
        volumes = [i.path for i in os.scandir("/Volumes")]
        rel_path = path.strip(os.sep).split(os.sep)
        rel_path = os.sep.join(rel_path[2:])
        for i in volumes:
            new_path = os.path.join(i, rel_path)
            if os.path.exists(new_path):
                return new_path
        return path


class ClipboardItemGlob:
    src_urls: list[str] = []
    is_cut: bool = False
    is_search: bool = False
    src_dir: str = ""
    dst_dir: str = ""
    
    @classmethod
    def set_is_cut(cls, value: bool):
        cls.is_cut = value

    @classmethod
    def reset(cls):
        cls.src_urls = []
        cls.is_cut = False
        cls.is_search = False
        cls.src_dir = ""
        cls.dst_dir = ""


@dataclass(slots=True)
class DirItem:
    data_items: list[DataItem]
    main_win_item: MainWinItem
    sort_item: SortItem


@dataclass(slots=True)
class JpgConvertItem:
    current_count: int
    current_filename: str
    msg: Literal["", "finished"]
    urls: list[str]


@dataclass(slots=True)
class MultipleInfoItem:
    total_size: int
    total_files: int
    total_folders: int
    folders: set
    files: set


@dataclass(slots=True)
class SearchItem:
    # список для поиска:
    # айтем в нижнем регистре: оригинальный айтем
    search_list: dict[str, str]
    # по мере поиска файлов, если файл найден, то он удаляется из
    # missed files, и в конце поиска в missed files останутся только
    # ненайденные файлы
    missed_files: dict[str, str]

    root_dir: str
    queue: Queue
    engine: sqlalchemy.Engine

    # SINGLE DIR
    # эти данные нужны когда поиск сканирует директорию
    # данные динамически обновляются для новой директории
    # смотри system multiprocess SearchTask
    fs_id: str
    rel_parent: str
    db_items: dict
    new_items: list[DataItem]


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


@dataclass(slots=True)
class ImgViewItem:
    start_url: str
    url_to_wid: dict[str, object]
    is_selection: bool