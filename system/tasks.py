import difflib
import gc
import os
import shutil
from collections import Counter, defaultdict
from time import sleep

import numpy as np
import sqlalchemy
from PIL import Image
from PyQt5.QtCore import QObject, QTimer, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtTest import QTest
from sqlalchemy.exc import IntegrityError, OperationalError

from cfg import JsonData, Static, ThumbData
from evlosh_templates.evlosh_utils import EvloshUtils
from evlosh_templates.fit_image import FitImage
from evlosh_templates.path_finder import PathFinder
from evlosh_templates.read_image import ReadImage

from .database import CACHE, Dbase
from .items import (AnyBaseItem, BaseItem, CopyItem, ImageBaseItem,
                    MainWinItem, SearchItem, SortItem)
from .utils import ImageUtils, URunnable, Utils
import zipfile

# Общий класс для выполнения действий QAction в отдельном потоке
class ActionsTask(URunnable):
    def __init__(self,  cmd_: callable):
        super().__init__()
        self.cmd_ = cmd_

    def task(self):
        self.cmd_()


class _CopyFilesSigs(QObject):
    finished_ = pyqtSignal(list)
    set_copied_kb = pyqtSignal(int)
    set_total_kb = pyqtSignal(int)
    set_counter = pyqtSignal(tuple)
    error_win = pyqtSignal()
    replace_files_win = pyqtSignal()


class CopyFilesTask(URunnable):
    def __init__(self):
        super().__init__()
        self.sigs = _CopyFilesSigs()
        self.pause_flag = False
        self.copied_kb = 0
        self.thumb_paths: list[str] = []
        self.src_dest_list: list[tuple[str, str]] = []

        self.copied_timer = QTimer()
        self.copied_timer.timeout.connect(self.send_copied_kb)
        self.copied_timer.start(1000)

    def prepare_same_dir(self):
        """
        Если файлы и папки скопированы в одной директории и будут вставлены туда же,
        то они будут вставлены с припиской "копия"
        """
        for src_url in CopyItem.urls:
            if os.path.isfile(src_url):
                new_filename = self.add_copy_to_name(src_url)
                self.src_dest_list.append((src_url, new_filename))
                self.thumb_paths.append(new_filename)
            else:
                new_dir_name = self.add_copy_to_name(src_url)
                # получаем все url файлов для папки
                # заменяем имя старой папки на имя новой папки
                nested_urls = [
                    (x, x.replace(src_url, new_dir_name))
                    for x in self.get_nested_urls(src_url)
                ]
                self.src_dest_list.extend(nested_urls)
                self.thumb_paths.append(new_dir_name)
    
    def prepare_another_dir(self):
        """
        Подготовка к простому копированию из одного места в другое.
        При этом может выскочить окно о замене файлов, и если 
        пользователь не согласится заменить файлы, задача копирования будет
        отменена.
        """
        for src_url in CopyItem.urls:
            if os.path.isfile(src_url):
                new_filename = src_url.replace(CopyItem.get_src(), CopyItem.get_dest())
                self.src_dest_list.append((src_url, new_filename))
                self.thumb_paths.append(new_filename)
            else:
                new_dir_name = src_url.replace(CopyItem.get_src(), CopyItem.get_dest())
                # получаем все url файлов для папки
                # заменяем имя старой папки на имя новой папки
                nested_urls = [
                    (x, x.replace(CopyItem.get_src(), CopyItem.get_dest()))
                    for x in self.get_nested_urls(src_url)
                ]
                self.src_dest_list.extend(nested_urls)
                self.thumb_paths.append(new_dir_name)

        for src, dest in self.src_dest_list:
            if os.path.exists(dest):
                self.sigs.replace_files_win.emit()
                self.pause_flag = True
                while self.pause_flag:
                    sleep(1)
                break

    def prepare_search_dir(self):
        existing_paths = set()

        for url in CopyItem.urls:
            filename = os.path.basename(url)
            dest_dir = CopyItem.get_dest()
            base_name, ext = os.path.splitext(filename)

            new_name = filename
            count = 2
            full_path = os.path.join(dest_dir, new_name)

            while full_path in existing_paths:
                new_name = f"{base_name} {count}{ext}"
                full_path = os.path.join(dest_dir, new_name)
                count += 1

            existing_paths.add(full_path)
            self.src_dest_list.append((url, full_path))
            self.thumb_paths.append(full_path)

    def task(self):
        if CopyItem.get_is_search():
            self.prepare_search_dir()
        elif CopyItem.get_src() == CopyItem.get_dest():
            self.prepare_same_dir()
        else:
            self.prepare_another_dir()

        # for i in self.src_dest_list:
        #     print(i)

        total_bytes = 0
        for src, dest in self.src_dest_list:
            total_bytes += os.path.getsize(src)
        try:
            self.sigs.set_total_kb.emit(self.bytes_to_kb(total_bytes))
        except RuntimeError as e:
            Utils.print_error()
            return

        for count, (src, dest) in enumerate(self.src_dest_list, start=1):
            if not self.is_should_run():
                break
            data = (count, len(self.src_dest_list))
            self.sigs.set_counter.emit(data)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            try:
                self.copy_by_bytes(src, dest)
            except Exception as e:
                Utils.print_error()
                self.sigs.error_win.emit()
                break
            if CopyItem.get_is_cut() and not CopyItem.get_is_search():
                if os.path.isdir(src):
                    shutil.rmtree(src)
                else:
                    os.remove(src)
        try:
            self.sigs.finished_.emit(self.thumb_paths)
        except RuntimeError as e:
            Utils.print_error()

    def bytes_to_kb(self, bytes: int):
        return int(bytes / (1024 * 1024))

    def add_copy_to_name(self, url: str):
        dir_name, file_name = os.path.split(url)
        name, ext = os.path.splitext(file_name)
        new_name = f"{name} копия{ext}"
        return os.path.join(dir_name, new_name)

    def get_nested_urls(self, src_dir: str):
        stack = [src_dir]
        nested_paths: list[str] = []
        while stack:
            current_dir = stack.pop()
            for dir_entry in os.scandir(current_dir):
                if dir_entry.is_dir():
                    stack.append(dir_entry.path)
                else:
                    nested_paths.append(dir_entry.path)
        return nested_paths

    def copy_by_bytes(self, src: str, dest: str):
        tmp = True
        buffer_size = 1024 * 1024  # 1 MB
        with open(src, 'rb') as fsrc, open(dest, 'wb') as fdest:
            while tmp:
                buf = fsrc.read(buffer_size)
                if not buf:
                    break
                if not self.is_should_run():
                    return
                fdest.write(buf)
                # прибавляем в байтах сколько уже скопировано
                buf = self.bytes_to_kb(len(buf))
                self.copied_kb += buf
    
    def send_copied_kb(self):
        try:
            self.sigs.set_copied_kb.emit(self.copied_kb)
        except RuntimeError:
            ...

class _RatingSigs(QObject):
    finished_ = pyqtSignal()


class RatingTask(URunnable):
    def __init__(self, main_dir: str, filename: str, new_rating: int):
        super().__init__()
        self.filename = filename
        self.new_rating = new_rating
        self.main_dir = main_dir
        self.sigs = _RatingSigs()

    def task(self):        
        db = os.path.join(self.main_dir, Static.DB_FILENAME)
        dbase = Dbase()
        engine = dbase.create_engine(path=db)
        if engine is None:
            return
        conn = Dbase.open_connection(engine)
        hash_filename = Utils.get_hash_filename(self.filename)
        stmt = sqlalchemy.update(CACHE)
        stmt = stmt.where(CACHE.c.name==hash_filename)
        stmt = stmt.values(rating=self.new_rating)
        Dbase.execute_(conn, stmt)
        Dbase.commit_(conn)
        self.sigs.finished_.emit()
        Dbase.close_connection(conn)


class _SearchSigs(QObject):
    new_widget = pyqtSignal(BaseItem)
    finished_ = pyqtSignal(list)


class SearchTask(URunnable):
    sleep_ms = 1000
    new_wid_sleep_ms = 200
    ratio = 0.85

    def __init__(self, main_win_item: MainWinItem, search_item: SearchItem):
        super().__init__()
        self.sigs = _SearchSigs()
        self.main_win_item = main_win_item
        self.found_files_list: list[str] = []

        self.search_item = search_item
        self.files_list_lower: list[str] = []
        self.text_lower: str = None
        self.exts_lower: tuple[str] = None

        self.db_path: str = None
        self.conn = None
        self.pause = False

    def task(self):
        self.setup_search()
        self.scandir_recursive()
        
        missed_files_list: list[str] = []

        if isinstance(self.search_item.get_content(), list):
            if self.is_should_run():

                no_ext_list = [
                    os.path.splitext(i)[0]
                    for i in self.search_item.get_content()
                ]

                for i in no_ext_list:
                    if i not in self.found_files_list:
                        missed_files_list.append(i)

        try:
            self.sigs.finished_.emit(missed_files_list)
        except RuntimeError as e:
            Utils.print_error()
            self.set_should_run(False)


    def setup_search(self):
        if isinstance(self.search_item.get_content(), list):
            if self.search_item.get_filter() == 0:
                self.process_entry = self.process_list_free
            elif self.search_item.get_filter() == 1:
                self.process_entry = self.process_list_exactly
            else:
                self.process_entry = self.process_list_contains

            for i in self.search_item.get_content():
                filename, _ = self.remove_extension(i)
                self.files_list_lower.append(filename.lower())

        elif isinstance(self.search_item.get_content(), tuple):
            self.process_entry = self.process_extensions
            exts_lower = (i.lower() for i in self.search_item.get_content())
            self.exts_lower = tuple(exts_lower)

        elif isinstance(self.search_item.get_content(), str):
            if self.search_item.get_filter() == 0:
                self.process_entry = self.process_text_free
            elif self.search_item.get_filter() == 1:
                self.process_entry = self.process_text_exactly
            else:
                self.process_entry = self.process_text_contains

            self.text_lower = self.search_item.get_content().lower()
    
    def remove_extension(self, filename: str):
        return os.path.splitext(filename)
        
    # базовый метод обработки os.DirEntry
    def process_entry(self, entry: os.DirEntry): ...

    def process_extensions(self, entry: os.DirEntry):
        path = entry.path
        path: str = path.lower()
        if path.endswith(self.exts_lower):
            return True
        else:
            return False

    def process_text_free(self, entry: os.DirEntry):
        filename, _ = self.remove_extension(entry.name)
        filename: str = filename.lower()
        if self.similarity_ratio(self.text_lower, filename) > SearchTask.ratio:
            return True
        else:
            return False
        
    def process_text_exactly(self, entry: os.DirEntry):
        filename, _ = self.remove_extension(entry.name)
        filename: str = filename.lower()
        if filename == self.text_lower:
            return True
        else:
            return False

    def process_text_contains(self, entry: os.DirEntry):
        filename, _ = self.remove_extension(entry.name)
        filename: str = filename.lower()
        if self.text_lower in filename or filename in self.text_lower:
            return True
        else:
            return False

    def process_list_exactly(self, entry: os.DirEntry):
        true_filename, _ = self.remove_extension(entry.name)
        filename: str = true_filename.lower()
        for item in self.files_list_lower:
            if filename == item:
                self.found_files_list.append(true_filename)
                return True
        return False

    def process_list_free(self, entry: os.DirEntry):
        true_filename, _ = self.remove_extension(entry.name)
        filename: str = true_filename.lower()
        for item in self.files_list_lower:
            if self.similarity_ratio(item, filename) > SearchTask.ratio:
                self.found_files_list.append(true_filename)
                return True
        return False

    def process_list_contains(self, entry: os.DirEntry):
        true_filename, _ = self.remove_extension(entry.name)
        filename: str = true_filename.lower()
        for item in self.files_list_lower:
            if item in filename or filename in item:
                self.found_files_list.append(true_filename)
                return True
        return False

    def similarity_ratio(self, a: str, b: str) -> float:
        return difflib.SequenceMatcher(None, a, b).ratio()

    def scandir_recursive(self):
        # Инициализируем список с корневым каталогом
        dirs_list = [self.main_win_item.main_dir]

        while dirs_list:
            current_dir = dirs_list.pop()

            while self.pause:
                QTest.qSleep(SearchTask.sleep_ms)
                if not self.is_should_run():
                    return

            if not self.is_should_run():
                return

            if not os.path.exists(current_dir):
                continue

            try:
                # Сканируем текущий каталог и добавляем новые пути в стек
                self.scan_current_dir(current_dir, dirs_list)
            except OSError as e:
                Utils.print_error()
                continue
            except Exception as e:
                Utils.print_error()
                continue
            except RuntimeError as e:
                Utils.print_error()
                return

    def scan_current_dir(self, dir: str, dirs_list: list):
        for entry in os.scandir(dir):
            while self.pause:
                QTest.qSleep(SearchTask.sleep_ms)
                if not self.is_should_run():
                    return
            if not self.is_should_run():
                return
            if entry.name.startswith(Static.hidden_file_syms):
                continue
            if entry.is_dir():
                dirs_list.append(entry.path)
                continue
            if self.process_entry(entry):
                self.process_img(entry)

    def process_img(self, entry: os.DirEntry):
        base_item = BaseItem(entry.path)
        base_item.set_properties()
        if entry.name.endswith(Static.ext_all):
            img_array = ReadImage.read_image(entry.path)
            img_array = FitImage.start(img_array, ThumbData.DB_IMAGE_SIZE)
            pixmap = ImageUtils.pixmap_from_array(img_array)
            base_item.set_pixmap_storage(pixmap)
        try:
            self.sigs.new_widget.emit(base_item)
            QTest.qSleep(SearchTask.new_wid_sleep_ms)
        except RuntimeError:
            self.set_should_run(False)


class _FinderSigs(QObject):
    finished_ = pyqtSignal(list)


class FinderItems(URunnable):
    hidden_syms: tuple[str] = ()
    sql_errors = (IntegrityError, OperationalError)

    def __init__(self, main_win_item: MainWinItem, sort_item: SortItem):
        super().__init__()
        self.sigs = _FinderSigs()
        self.sort_item = sort_item
        self.main_win_item = main_win_item

        self.finder_base_items: dict[str, BaseItem] = {}
        self.db_items: dict[str, int] = {}
        self.conn = self.create_connection()

        if not JsonData.show_hidden:
            self.hidden_syms = Static.hidden_file_syms

    def task(self):
        try:
            self.finder_base_items = self.get_finder_base_items()
        except Exception:
            Utils.print_error()
        try:
            if self.conn:
                self.db_items = self.get_db_items()
                self.delete_removed_items()
                self.set_base_item_rating()
        except self.sql_errors:
            Utils.print_error()

        finder_base_items = list(self.finder_base_items.values())
        finder_base_items = BaseItem.sort_items(finder_base_items, self.sort_item)

        try:
            self.sigs.finished_.emit(finder_base_items)
        except RuntimeError as e:
            Utils.print_error()

    def get_db_items(self) -> dict[str, int]:
        q = sqlalchemy.select(CACHE.c.name, CACHE.c.rating)
        return {
            hash_filename: rating
            for hash_filename, rating in self.conn.execute(q).fetchall()
        }

    def delete_removed_items(self):
        """
        Сравнивает хеш имена Finder и хеш имена в базе данных
        Удаляет те, которых больше нет в Finder
        """
        for hash_filename, rating in self.db_items.items():
            if hash_filename not in self.finder_base_items:
                q = sqlalchemy.delete(CACHE).where(CACHE.c.name == hash_filename)
                self.conn.execute(q)
        self.conn.commit()

    def create_connection(self) -> sqlalchemy.Connection | None:
        db = os.path.join(self.main_win_item.main_dir, Static.DB_FILENAME)
        dbase = Dbase()
        engine = dbase.create_engine(path=db)
        if engine is None:
            return None
        else:
            return Dbase.open_connection(engine)

    def get_finder_base_items(self) -> dict[str, BaseItem]:
        """
        Сканирует текущую директорию
        Возвращает словарь: хеш имени файла: BaseItem
        """
        base_items = {}
        for entry in os.scandir(self.main_win_item.main_dir):
            if entry.name.startswith(self.hidden_syms):
                continue
            base_item = BaseItem(entry.path)
            base_item.set_properties()
            hash_filename = Utils.get_hash_filename(base_item.filename)
            base_items[hash_filename] = base_item
        return base_items
    
    def set_base_item_rating(self):
        """
        Если BaseItem есть в базе данных, то устанавливается рейтинг из базы данных
        """
        for hash_filename, rating in self.db_items.items():
            base_item = self.finder_base_items.get(hash_filename, None)
            if base_item:
                base_item.rating = rating
    

class _LoadImagesSigs(QObject):
    update_thumb = pyqtSignal(BaseItem) # на самом деле Thumb
    finished_ = pyqtSignal()


class LoadImagesTask(URunnable):
    def __init__(self, main_win_item: MainWinItem, thumbs: list[BaseItem]):
        """
        URunnable   
        Сортирует список Thumb по размеру по возрастанию для ускорения загрузки
        Загружает изображения из базы данных или создает новые
        """
        super().__init__()
        self.sigs = _LoadImagesSigs()
        self.main_win_item = main_win_item
        self.stmt_list: list[sqlalchemy.Insert | sqlalchemy.Update] = []
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
            self.sigs.finished_.emit()
        except RuntimeError as e:
            Utils.print_error()

    def process_thumbs(self):
        """
        Обходит циклом список Thumb     
        Пытается загрузить изображение из базы данных или создает новое,
        чтобы передать его в Thumb
        """
        for thumb in self.thumbs:
            if not self.is_should_run():
                return  
            if thumb.type_ not in Static.ext_all:
                any_base_item = AnyBaseItem(self.conn, thumb)
                stmt = any_base_item.get_stmt()
                if stmt is not None:
                    self.stmt_list.append(stmt)
            else:
                img_base_item = ImageBaseItem(self.conn, thumb)
                stmt, pixmap = img_base_item.get_stmt_pixmap()
                if pixmap:
                    thumb.set_pixmap_storage(pixmap)
                if stmt is not None:
                    self.stmt_list.append(stmt)
                try:
                    self.sigs.update_thumb.emit(thumb)
                except (TypeError, RuntimeError, TypeError) as e:
                    Utils.print_error()
                    return
                
    def process_stmt_list(self):
        for stmt in self.stmt_list:
            if not Dbase.execute_(self.conn, stmt):
                return
        Dbase.commit_(self.conn)



class _LoadThumbSigs(QObject):
    finished_ = pyqtSignal(tuple)


class LoadThumbTask(URunnable):
    def __init__(self, src: str):
        super().__init__()
        self.sigs = _LoadThumbSigs()
        self.src = EvloshUtils.norm_slash(src)
        self.name = os.path.basename(self.src)

    def task(self):
        db = os.path.join(os.path.dirname(self.src), Static.DB_FILENAME)
        dbase = Dbase()
        engine = dbase.create_engine(path=db)

        if engine is None:
            image_data = (self.src, None)
            self.sigs.finished_.emit(image_data)
            return

        conn = Dbase.open_connection(engine)

        q = sqlalchemy.select(CACHE.c.img)
        q = q.where(CACHE.c.name == Utils.get_hash_filename(self.name))
        res = conn.execute(q).scalar() or None

        Dbase.close_connection(conn)

        if res is not None:
            img_array = ImageUtils.bytes_to_array(res)
            img_array = ImageUtils.desaturate_image(img_array, 0.2)
        else:
            img_array = None

        if img_array is None:
            pixmap = None

        else:
            pixmap = ImageUtils.pixmap_from_array(img_array)

        image_data = (self.src, pixmap)

        try:
            self.sigs.finished_.emit(image_data)
        except RuntimeError as e:
            Utils.print_error()


class LoadImageTask(URunnable):
    cache_limit = 15
    cached_images: dict[str, QPixmap] = {}

    def __init__(self, src: str):
        super().__init__()
        self.sigs = _LoadThumbSigs()
        self.src: str = src

    def task(self):
        if self.src not in self.cached_images:

            img_array = ReadImage.read_image(self.src)
            img_array = ImageUtils.desaturate_image(img_array, 0.2)

            if img_array is None:
                pixmap = None

            else:
                pixmap = ImageUtils.pixmap_from_array(img_array)
                self.cached_images[self.src] = pixmap

            del img_array
            gc.collect()

        else:
            pixmap = self.cached_images.get(self.src)
        if len(self.cached_images) > self.cache_limit:
            self.cached_images.pop(list(self.cached_images)[0])

        image_data = (self.src, pixmap)
        self.sigs.finished_.emit(image_data)


class _InfoTaskSigs(QObject):
    finished_info = pyqtSignal(dict)
    finished_calc = pyqtSignal(str)


class ImgResolTask(URunnable):
    undef_text = "Неизвестно"

    def __init__(self, base_item: BaseItem):
        super().__init__()
        self.base_item = base_item
        self.sigs = _InfoTaskSigs()

    def task(self):
        img_ = ReadImage.read_image(self.base_item.src)
        if img_ is not None and len(img_.shape) > 1:
            h, w = img_.shape[0], img_.shape[1]
            resol= f"{w}x{h}"
        else:
            resol = self.undef_text
        
        self.sigs.finished_calc.emit(resol)


class FolderSizeTask(URunnable):
    undef_text = "Неизвестно"

    def __init__(self, base_item: BaseItem):
        super().__init__()
        self.base_item = base_item
        self.sigs = _InfoTaskSigs()

    def task(self):
        try:
            total = self.get_folder_size()
        except Exception:
            Utils.print_error()
            total = self.undef_text

        self.sigs.finished_calc.emit(total)

    def get_folder_size(self):
        total = 0
        stack = []
        stack.append(self.base_item.src)
        while stack:
            current_dir = stack.pop()
            with os.scandir(current_dir) as entries:
                for entry in entries:
                    if entry.is_dir():
                        stack.append(entry.path)
                    else:
                        total += entry.stat().st_size
        return EvloshUtils.get_f_size(total)


class InfoTask(URunnable):
    ru_folder = "Папка"
    calculating = "Вычисляю..."
    name_text = "Имя"
    type_text = "Тип"
    size_text = "Размер"
    src_text = "Место"
    mod_text = "Изменен"
    resol_text = "Разрешение"
    row_limit = 50

    def __init__(self, base_item: BaseItem):
        super().__init__()
        self.base_item = base_item
        self.signals = _InfoTaskSigs()

    def task(self) -> dict[str, str| int]:
        if self.base_item.type_ == Static.FOLDER_TYPE:
            size_ = self.calculating
            type_ = self.ru_folder
        else:
            size_ = EvloshUtils.get_f_size(self.base_item.size)
            type_ = self.base_item.type_
        
        name = self.lined_text(self.base_item.filename)
        src = self.lined_text(self.base_item.src)
        mod = EvloshUtils.get_f_date(self.base_item.mod)

        data = {
            InfoTask.name_text: name,
            InfoTask.type_text: type_,
            InfoTask.mod_text: mod,
            InfoTask.src_text: src,
            InfoTask.size_text: size_,
            }
        
        if self.base_item.type_ != Static.FOLDER_TYPE:
            data.update({InfoTask.resol_text: self.calculating})

        self.signals.finished_info.emit(data)

    def lined_text(self, text: str):
        if len(text) > InfoTask.row_limit:
            text = [
                text[i:i + InfoTask.row_limit]
                for i in range(0, len(text), InfoTask.row_limit)
                ]
            return "\n".join(text)
        else:
            return text
        

class _RemoveFilesSigs(QObject):
    finished_ = pyqtSignal()


class RemoveFilesTask(URunnable):
    def __init__(self, main_dir: str, urls: list[str]):
        super().__init__()
        self.sigs = _RemoveFilesSigs()
        self.main_dir = main_dir
        self.urls = urls

    def task(self):
        try:
            for i in self.urls:
                try:
                    if os.path.isdir(i):
                        shutil.rmtree(i)
                    else:
                        os.remove(i)
                except Exception as e:
                    Utils.print_error()
        except Exception as e:
            Utils.print_error()
        try:
            self.sigs.finished_.emit()
        except RuntimeError as e:
            Utils.print_error()


class _PathFinderSigs(QObject):
    finished_ = pyqtSignal(str)


class PathFinderTask(URunnable):
    def __init__(self, path: str):
        super().__init__()
        self.path = path
        self.path_finder = PathFinder(path)
        self.sigs = _PathFinderSigs()

    def task(self):
        result = self.path_finder.get_result()
        if result is None:
            result = ""
        
        self.sigs.finished_.emit(result)


class _NewItemsSigs(QObject):
    new_wid = pyqtSignal(object)

class NewItems(URunnable):
    def __init__(self, main_win_item: MainWinItem, urls: list[str]):
        super().__init__()
        self.urls = urls
        self.main_win_item = main_win_item
        self.signals = _NewItemsSigs()

    def task(self):
        dbase = Dbase()
        engine = dbase.create_engine(self.main_win_item.main_dir)
        conn = Dbase.open_connection(engine)
        if not conn:
            return
        for i in self.urls:
            base_item = BaseItem(i)
            base_item.set_properties()
            if base_item.filename.endswith(Static.ext_all):
                image_base_item = ImageBaseItem(conn, base_item)
                stmt, pixmap = image_base_item.get_stmt_pixmap()
                if pixmap:
                    base_item.set_pixmap_storage(pixmap)
            else:
                any_base_item = AnyBaseItem(conn, base_item)
                stmt = any_base_item.get_stmt()

            if stmt:
                try:
                    conn.execute(stmt)
                    self.signals.new_wid.emit(base_item)
                except Exception:
                    conn.rollback()
                    continue
        try:
            conn.commit()
        except Exception:
            conn.rollback()
            ...
        conn.close()
        return super().task()
    

class _ImgConvertSigs(QObject):
    finished_ = pyqtSignal(list)
    progress_value = pyqtSignal(int)
    set_progress_len = pyqtSignal(int)


class ImgConvertTask(URunnable):
    def __init__(self, urls: list[str]):
        super().__init__()
        self.urls = urls
        self.new_urls: list[str] = []
        self.sigs = _ImgConvertSigs()

    def task(self):
        urls = [
            i
            for i in self.urls
            if i.endswith(Static.ext_all)
        ]

        try:
            self.sigs.set_progress_len.emit(len(urls))
        except RuntimeError:
            return

        for x, url in enumerate(urls, start=1):
            save_path = self._save_jpg(url)
            if save_path:
                self.new_urls.append(save_path)

            try:
                self.sigs.progress_value.emit(x)
            except RuntimeError:
                break

        try:
            self.sigs.finished_.emit(self.new_urls)
        except RuntimeError:
            ...

        print("finished")

    def _save_jpg(self, src: str) -> None:
        try:
            img_array = ReadImage.read_image(src)
            img = Image.fromarray(img_array.astype(np.uint8))
            save_path = os.path.splitext(src)[0] + ".jpg"
            img.save(save_path, format="JPEG", quality=99)
            return save_path
        except Exception:
            Utils.print_error()
            return None
        

class _ArchiveSigs(QObject):
    set_max = pyqtSignal(int)
    set_value = pyqtSignal(int)
    finished_ = pyqtSignal(str)


class Archive(URunnable):
    def __init__(self, files: list[str], zip_path: str):
        super().__init__()
        self.sigs = _ArchiveSigs()
        self.files = files
        self.zip_path = zip_path
        self.progress = 0
        self.all_files = self._collect_all_files()

    def _collect_all_files(self) -> list[tuple[str, str]]:
        """
        Собираем список всех файлов для архива.
        Возвращаем список кортежей (полный_путь, путь_в_архиве).
        """
        collected = []
        for item in self.files:
            if os.path.isfile(item):
                collected.append((item, os.path.basename(item)))
            elif os.path.isdir(item):
                base_dir = os.path.dirname(item)
                for root, _, files in os.walk(item):
                    for f in files:
                        full_path = os.path.join(root, f)
                        rel_path = os.path.relpath(full_path, start=base_dir)
                        collected.append((full_path, rel_path))
        return collected

    def _add_file(self, zf, full_path, arc_path):
        """Добавляем файл и обновляем прогресс."""
        zf.write(full_path, arcname=arc_path)
        self.progress += 1
        self.sigs.set_value.emit(self.progress)

    def zip_items(self):
        """Архивация уже собранного списка файлов."""
        self.sigs.set_max.emit(len(self.all_files))
        self.progress = 0

        with zipfile.ZipFile(self.zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for full_path, arc_path in self.all_files:
                self._add_file(zf, full_path, arc_path)

    def task(self):
        """Метод для потока."""
        self.zip_items()
        self.sigs.finished_.emit(self.zip_path)
