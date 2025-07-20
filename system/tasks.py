import difflib
import gc
import os
import shutil
from time import sleep

import sqlalchemy
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtTest import QTest
from sqlalchemy.exc import IntegrityError, OperationalError

from cfg import JsonData, Static, ThumbData
from evlosh_templates.evlosh_utils import EvloshUtils
from evlosh_templates.fit_image import FitImage
from evlosh_templates.path_finder import PathFinder
from evlosh_templates.read_image import ReadImage

from .database import CACHE, Dbase
from .items import (AnyBaseItem, BaseItem, ImageBaseItem, MainWinItem,
                    SearchItem, SortItem)
from .utils import UImage, URunnable, Utils


# Общий класс для выполнения действий QAction в отдельном потоке
class ActionsTask(URunnable):
    def __init__(self,  cmd_: callable):
        super().__init__()
        self.cmd_ = cmd_

    def task(self):
        self.cmd_()


class _CopyFilesSigs(QObject):
    finished_ = pyqtSignal(list)
    set_value = pyqtSignal(int)
    set_size_mb = pyqtSignal(str)
    set_max = pyqtSignal(int)
    error_ = pyqtSignal()
    replace_files = pyqtSignal()


class CopyFilesTask(URunnable):
    def __init__(self, dest: str, urls: list[str]):
        super().__init__()
        self.dest = dest
        self.urls = urls
        self.pause_flag = False
        self.cancel_flag = False
        self.signals_ = _CopyFilesSigs()

    def task(self): 
        try:
            new_paths = self.create_new_paths()
            for src_path, new_path in new_paths:
                if os.path.exists(new_path):
                    self.pause_flag = True
                    self.signals_.replace_files.emit()
                    while self.pause_flag:
                        sleep(1)
                    if self.cancel_flag:
                        self.signals_.finished_.emit([])
                        return
                    else:
                        break

        except OSError as e:
            Utils.print_error()
            try:
                self.signals_.error_.emit()
            except RuntimeError as e:
                # прерываем процесс, если родительский виджет был уничтожен
                Utils.print_error()
                return

        # общий размер всех файлов в байтах
        total_bytes = sum([os.path.getsize(old_path)for old_path, new_path in new_paths])

        # общий размер всех файлов в МБ для установки максимального
        # значения QProgressbar (в байтах плохо работает)
        total_mb = int(total_bytes / (1024 * 1024))

        try:
            self.signals_.set_max.emit(total_mb)
        except RuntimeError as e:
            Utils.print_error()
            return

        # сколько уже скопировано в байтах
        self.copied_bytes = 0
        
        # байты переводим в читаемый f string
        self.total_f_size = EvloshUtils.get_f_size(total_bytes)

        for src, dest in new_paths:
            # создаем древо папок как в исходной папке
            new_folders, tail = os.path.split(dest)
            os.makedirs(new_folders, exist_ok=True)
            try:
                self.copy_by_bytes(src, dest)
            except IOError as e:
                Utils.print_error()
                continue
            except Exception as e:
                Utils.print_error()
                self.signals_.error_.emit()
                return

        # создаем список путей к виджетам в сетке для выделения
        paths = self.get_final_paths(new_paths, self.dest)
        paths = list(paths)

        try:
            self.signals_.finished_.emit(paths)
        except RuntimeError as e:
            Utils.print_error()

    def copy_by_bytes(self, src: str, dest: str):
        tmp = True
        buffer_size = 1024 * 1024  # 1 MB
        mb_count_update = 5
        report_interval = mb_count_update * 1024 * 1024  # 5 MB
        reported_bytes = 0
        with open(src, 'rb') as fsrc, open(dest, 'wb') as fdest:
            while tmp:
                buf = fsrc.read(buffer_size)
                if not buf:
                    break
                fdest.write(buf)
                # прибавляем в байтах сколько уже скопировано
                self.copied_bytes += len(buf)
                reported_bytes += len(buf)  # <-- вот это добавь

                if reported_bytes >= report_interval:
                    try:
                        self.report_progress()
                    except RuntimeError as e:
                        Utils.print_error()
                        return
                    reported_bytes = 0

    def report_progress(self):
        # сколько уже скопировано в байтах переводим в МБ, потому что
        # максимальное число QProgressbar задано тоже в МБ
        copied_mb = int(self.copied_bytes / (1024 * 1024))
        self.signals_.set_value.emit(copied_mb)

        # байты переводим в читаемый f string
        copied_f_size = EvloshUtils.get_f_size(self.copied_bytes)

        text = f"{copied_f_size} из {self.total_f_size}"
        self.signals_.set_size_mb.emit(text)

    def get_final_paths(self, new_paths: list[tuple[str, str]], root: str):
        # Например мы копируем папки test_images и abs_images с рабочего стола в папку загрузок
        # Внутри test_images и abs есть разные файлы и папки
        # 
        # /Users/Some_user/Desktop/test_images/path/to/file.jpg
        # /Users/Some_user/Desktop/test_images/path/to/file 2.jpg
        # /Users/Some_user/Desktop/test_images/path/to/file 2.jpg
        # 
        # /Users/Some_user/Desktop/abs_images/path/to/file.jpg
        # /Users/Some_user/Desktop/abs_imagesges/path/to/file 2.jpg
        # /Users/Some_user/Desktop/abs_images/path/to/file 2.jpg
        # 
        # Наша задача получить сет из следующих элементов:
        # /Users/Some_user/Downloasd/test_images
        # /Users/Some_user/Downloads/abs_image
        # 
        # Сет передается в сигнал finished, где _grid.py выделит виджеты в
        # сетке, соответствующие директориям в сете.
        result = set()
        for old_path, new_path in new_paths:
            rel = os.path.relpath(new_path, root)
            first_part = rel.split(os.sep)[0]
            result.add(os.path.join(root, first_part))
        return result

    def create_new_paths(self):
        """
        [(src path, new path), ...]
        """
        self.old_new_paths: list[tuple[str, str]] = []
        self.new_paths = []

        for i in self.urls:
            i = EvloshUtils.normalize_slash(i)
            if os.path.isdir(i):
                self.old_new_paths.extend(self.scan_folder(i, self.dest))
            else:
                src, new_path = self.single_file(i, self.dest)
                if new_path in self.new_paths:
                    new_path = self.add_counter(new_path)
                self.new_paths.append(new_path)
                self.old_new_paths.append((src, new_path))

        return self.old_new_paths
    
    def add_counter(self, path: str):
        counter = 1
        base_root, ext = os.path.splitext(path)
        root = base_root
        while path in self.new_paths:
            path = f"{root} {counter}{ext}"
            counter += 1
        return path

    def single_file(self, file: str, dest: str):
        # Возвращает кортеж: исходный путь файла, финальный путь файла
        filename = os.path.basename(file)
        return (file, os.path.join(dest, filename))

    def scan_folder(self, src_dir: str, dest: str):
        # Рекурсивно сканирует папку src_dir.
        # Возвращает список кортежей: (путь к исходному файлу, путь назначения).
        # 
        # Путь назначения формируется так:
        # - Берётся относительный путь файла относительно родительской папки src_dir
        # - Этот относительный путь добавляется к пути назначения dest
        stack = [src_dir]
        new_paths: list[tuple[str, str]] = []

        src_dir = EvloshUtils.normalize_slash(src_dir)
        dest = EvloshUtils.normalize_slash(dest)

        # Родительская папка от src_dir — нужна, чтобы определить
        # относительный путь каждого файла внутри src_dir
        parent = os.path.dirname(src_dir)

        while stack:
            current_dir = stack.pop()
            for dir_entry in os.scandir(current_dir):
                if dir_entry.is_dir():
                    stack.append(dir_entry.path)
                else:
                    rel_path = dir_entry.path.split(parent)[-1]
                    new_path = dest + rel_path
                    new_paths.append((dir_entry.path, new_path))

        return new_paths
    

class _RatingSigs(QObject):
    finished_ = pyqtSignal()


class RatingTask(URunnable):
    def __init__(self, main_dir: str, filename: str, new_rating: int):
        super().__init__()
        self.filename = filename
        self.new_rating = new_rating
        self.main_dir = main_dir
        self.signals_ = _RatingSigs()

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
        self.signals_.finished_.emit()
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
        self.signals_ = _SearchSigs()
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
            self.signals_.finished_.emit(missed_files_list)
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
        self.img_array = ReadImage.read_image(entry.path)
        self.img_array = FitImage.start(self.img_array, ThumbData.DB_IMAGE_SIZE)
        self.pixmap = UImage.pixmap_from_array(self.img_array)
        self.base_item = BaseItem(entry.path)
        self.base_item.setup_attrs()
        self.base_item.set_pixmap_storage(self.pixmap)
        try:
            self.signals_.new_widget.emit(self.base_item)
            QTest.qSleep(SearchTask.new_wid_sleep_ms)
        except RuntimeError:
            self.set_should_run(False)


class _FinderSigs(QObject):
    finished_ = pyqtSignal(tuple)


class FinderItems(URunnable):
    hidden_syms: tuple[str] = None
    sql_errors = (IntegrityError, OperationalError)

    def __init__(self, main_win_item: MainWinItem, sort_item: SortItem):
        super().__init__()
        self.signals_ = _FinderSigs()
        self.sort_item = sort_item
        self.main_win_item = main_win_item

        if JsonData.show_hidden:
            FinderItems.hidden_syms = ()
        else:
            FinderItems.hidden_syms = Static.hidden_file_syms

    def task(self):
        try:
            base_items = self.get_base_items()
            conn = self.create_connection()
            if conn:
                base_items, new_items = self.set_rating(conn, base_items)
            else:
                base_items, new_items = self.get_items_no_db()
        except FinderItems.sql_errors as e:
            Utils.print_error()
            base_items, new_items = self.get_items_no_db()
        except Exception as e:
            Utils.print_error()
            base_items, new_items = [], []

        base_items = BaseItem.sort_(base_items, self.sort_item)
        new_items = BaseItem.sort_(new_items, self.sort_item)
        try:
            self.signals_.finished_.emit((base_items, new_items))
        except RuntimeError as e:
            Utils.print_error()

    def create_connection(self) -> sqlalchemy.Connection | None:
        db = os.path.join(self.main_win_item.main_dir, Static.DB_FILENAME)
        dbase = Dbase()
        engine = dbase.create_engine(path=db)
        if engine is None:
            return None
        else:
            return Dbase.open_connection(engine)

    def set_rating(self, conn: sqlalchemy.Connection, base_items: list[BaseItem]):
        """
        Устанавливает рейтинг для BaseItem, который затем передастся в Thumb    
        Рейтинг берется из базы данных
        """

        stmt = sqlalchemy.select(CACHE.c.name, CACHE.c.rating)
        res = Dbase.execute_(conn, stmt).fetchall()
        res = {name: rating for name, rating in res}

        new_files = []
        for i in base_items:
            name = Utils.get_hash_filename(i.name)
            if name in res:
                i.rating = res.get(name)
            else:
                new_files.append(i)

        return base_items, new_files

    def get_base_items(self) -> list[BaseItem]:
        base_items: list[BaseItem] = []
        with os.scandir(self.main_win_item.main_dir) as entries:
            for entry in entries:
                if entry.name.startswith(FinderItems.hidden_syms):
                    continue
                item = BaseItem(entry.path)
                item.setup_attrs()
                base_items.append(item)
        return base_items

    def get_items_no_db(self):
        base_items = []
        for entry in os.scandir(self.main_win_item.main_dir):
            if entry.name.startswith(FinderItems.hidden_syms):
                continue
            if entry.is_dir() or entry.name.endswith(Static.ext_all):
                item = BaseItem(entry.path)
                item.setup_attrs()
                base_items.append(item)
        return base_items, []
    

class _LoadImagesSigs(QObject):
    update_thumb = pyqtSignal(BaseItem)
    finished_ = pyqtSignal()


class LoadImages(URunnable):
    def __init__(self, main_win_item: MainWinItem, thumbs: list[BaseItem]):
        """
        URunnable   
        Сортирует список Thumb по размеру по возрастанию для ускорения загрузки
        Загружает изображения из базы данных или создает новые
        """
        super().__init__()
        self.signals_ = _LoadImagesSigs()
        self.main_win_item = main_win_item
        self.stmt_list: list[sqlalchemy.Insert | sqlalchemy.Update] = []
        self.base_items = thumbs
        key_ = lambda x: x.size
        self.base_items.sort(key=key_)

    def task(self):
        """
        Создает подключение к базе данных   
        Запускает обход списка Thumb для загрузки изображений   
        Испускает сигнал finished_
        """
        if not self.base_items:
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
            Utils.print_error()

    def process_thumbs(self):
        """
        Обходит циклом список Thumb     
        Пытается загрузить изображение из базы данных или создает новое,
        чтобы передать его в Thumb
        """
        for base_item in self.base_items:
            if not self.is_should_run():
                return  
            if base_item.type_ not in Static.ext_all:
                stmt, _ = AnyBaseItem.check_db_record(self.conn, base_item)
                if isinstance(stmt, sqlalchemy.Insert):
                    self.stmt_list.append(stmt)
            else:
                stmt, pixmap = ImageBaseItem.get_pixmap(self.conn, base_item)
                base_item.set_pixmap_storage(pixmap)
                if isinstance(stmt, (sqlalchemy.Insert, sqlalchemy.Update)):
                    self.stmt_list.append(stmt)
                try:
                    self.signals_.update_thumb.emit(base_item)
                except (TypeError, RuntimeError) as e:
                    Utils.print_error()
                    return
                
    def process_stmt_list(self):
        for stmt in self.stmt_list:
            if not Dbase.execute_(self.conn, stmt):
                return
        Dbase.commit_(self.conn)



class _LoadThumbSigs(QObject):
    finished_ = pyqtSignal(tuple)


class LoadThumb(URunnable):
    def __init__(self, src: str):
        super().__init__()
        self.signals_ = _LoadThumbSigs()
        self.src = EvloshUtils.normalize_slash(src)
        self.name = os.path.basename(self.src)

    def task(self):
        db = os.path.join(os.path.dirname(self.src), Static.DB_FILENAME)
        dbase = Dbase()
        engine = dbase.create_engine(path=db)

        if engine is None:
            image_data = (self.src, None)
            self.signals_.finished_.emit(image_data)
            return

        conn = Dbase.open_connection(engine)

        q = sqlalchemy.select(CACHE.c.img)
        q = q.where(CACHE.c.name == Utils.get_hash_filename(self.name))
        res = conn.execute(q).scalar() or None

        Dbase.close_connection(conn)

        if res is not None:
            img_array = UImage.bytes_to_array(res)
            img_array = UImage.desaturate_image(img_array, 0.2)
        else:
            img_array = None

        if img_array is None:
            pixmap = None

        else:
            pixmap = UImage.pixmap_from_array(img_array)

        image_data = (self.src, pixmap)

        try:
            self.signals_.finished_.emit(image_data)
        except RuntimeError as e:
            Utils.print_error()


class LoadImage(URunnable):
    cache_limit = 15
    cached_images: dict[str, QPixmap] = {}

    def __init__(self, src: str):
        super().__init__()
        self.signals_ = _LoadThumbSigs()
        self.src: str = src

    def task(self):
        if self.src not in self.cached_images:

            img_array = ReadImage.read_image(self.src)
            img_array = UImage.desaturate_image(img_array, 0.2)

            if img_array is None:
                pixmap = None

            else:
                pixmap = UImage.pixmap_from_array(img_array)
                self.cached_images[self.src] = pixmap

            del img_array
            gc.collect()

        else:
            pixmap = self.cached_images.get(self.src)
        if len(self.cached_images) > self.cache_limit:
            self.cached_images.pop(list(self.cached_images)[0])

        image_data = (self.src, pixmap)
        self.signals_.finished_.emit(image_data)


class _InfoTaskSigs(QObject):
    finished_info = pyqtSignal(dict)
    finished_calc = pyqtSignal(str)


class ImgResolTask(URunnable):
    undef_text = "Неизвестно"

    def __init__(self, base_item: BaseItem):
        super().__init__()
        self.base_item = base_item
        self.signals_ = _InfoTaskSigs()

    def task(self):
        img_ = ReadImage.read_image(self.base_item.src)
        if img_ is not None and len(img_.shape) > 1:
            h, w = img_.shape[0], img_.shape[1]
            resol= f"{w}x{h}"
        else:
            resol = self.undef_text
        
        self.signals_.finished_calc.emit(resol)


class FolderSizeTask(URunnable):
    undef_text = "Неизвестно"

    def __init__(self, base_item: BaseItem):
        super().__init__()
        self.base_item = base_item
        self.signals_ = _InfoTaskSigs()

    def task(self):
        try:
            total = self.get_folder_size()
        except Exception:
            Utils.print_error()
            total = self.undef_text

        self.signals_.finished_calc.emit(total)

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
        self.base_item.setup_attrs()

        if self.base_item.type_ == Static.FOLDER_TYPE:
            size_ = self.calculating
            type_ = self.ru_folder
        else:
            size_ = EvloshUtils.get_f_size(self.base_item.size)
            type_ = self.base_item.type_
        
        name = self.lined_text(self.base_item.name)
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
        self.signals_ = _RemoveFilesSigs()
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
            self.signals_.finished_.emit()
        except RuntimeError as e:
            Utils.print_error()


class _PathFinderSigs(QObject):
    finished_ = pyqtSignal(str)


class PathFinderTask(URunnable):
    def __init__(self, path: str):
        super().__init__()
        self.path = path
        self.path_finder = PathFinder(path)
        self.signals_ = _PathFinderSigs()

    def task(self):
        result = self.path_finder.get_result()
        if result is None:
            result = ""
        
        self.signals_.finished_.emit(result)