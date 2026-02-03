import os
import shutil
from multiprocessing import Process, Queue
from pathlib import Path
from time import sleep

import numpy as np
from PIL import Image
from sqlalchemy import Connection as Conn
from sqlalchemy import select
from watchdog.events import FileSystemEventHandler
from watchdog.observers.polling import PollingObserver as Observer

from cfg import Static
from system.database import Clmns, Dbase
from system.items import (CopyItem, DataItem, DirItem, JpgConvertItem,
                          MultipleInfoItem, SearchItem)
from system.shared_utils import ImgUtils, PathFinder, SharedUtils
from system.tasks import Utils


class BaseProcessWorker:
    def __init__(self, target: callable, args: tuple):
        super().__init__()

        self.proc = Process(
            target=target,
            args=(*args, )
        )

    def start(self):
        self.proc.start()

    def is_alive(self):
        return self.proc.is_alive()
    
    def terminate(self):
        """
        Корректно terminate с join
        Завершает все очереди Queue
        """
        self.proc.terminate()
        self.proc.join(timeout=0.2)
        queues: tuple[Queue] = (i for i in dir(self) if hasattr(i, "put"))
        for i in queues:
                i.close()
                i.join_thread()


class ProcessWorker(BaseProcessWorker):
    """
        Передает в BaseProcessWorker args + self.proc (Queue)
    """
    def __init__(self, target: callable, args: tuple):
        self.proc_q = Queue()
        super().__init__(target, (*args, self.proc_q))


class DirScaner:

    @staticmethod
    def start(dir_item: DirItem, q: Queue):
        try:
            DirScaner._start(dir_item, q)
        except Exception as e:
            print("system > multiprocess DirScaner error", e)
            q.put(dir_item)

    @staticmethod
    def _start(dir_item: DirItem, q: Queue):
        hidden_syms = () if dir_item._show_hidden else Static.hidden_symbols

        for entry in os.scandir(dir_item._main_win_item.main_dir):
            if entry.name.startswith(hidden_syms):
                continue
            if not os.access(entry.path, 4):
                continue

            data_item = DataItem(entry.path)
            data_item.set_properties()
            dir_item.data_items.append(data_item)

        dir_item.data_items = DataItem.sort_(dir_item.data_items, dir_item._sort_item)
        q.put(dir_item)


class ImgLoader:
    @staticmethod
    def start(data_items: list[DataItem], q: Queue):
        engine = Dbase.create_engine()
        conn = Dbase.get_conn(engine)

        data_items.sort(key=lambda x: x.size)
        stmt_list: list = []
        new_images: list[DataItem] = []
        exist_images: list[DataItem] = []
        svg_files: list[DataItem] = []
        exist_ratings: list[DataItem] = []

        for data_item in data_items:
            if data_item.image_is_loaded:
                continue
            if data_item.filename.endswith((".svg", ".SVG")):
                svg_files.append(data_item)
            elif data_item.type_ == Static.folder_type:
                rating = ImgLoader.get_item_rating(data_item, conn)
                if rating is None:
                    stmt_list.append(DataItem.insert_folder_stmt(data_item))
                else:
                    data_item.rating = rating
                    stmt_list.append(DataItem.update_folder_stmt(data_item))
                    exist_ratings.append(data_item)
            else:
                data_item.set_partial_hash()
                rating = ImgLoader.get_item_rating(data_item, conn)
                if rating is None:
                    stmt_list.append(DataItem.insert_file_stmt(data_item))
                    if data_item.type_ in ImgUtils.ext_all:
                        new_images.append(data_item)
                else:
                    data_item.rating = rating
                    stmt_list.append(DataItem.update_file_stmt(data_item))
                    if data_item.type_ in ImgUtils.ext_all:
                        if data_item.thumb_path and os.path.exists(data_item.thumb_path):
                            exist_images.append(data_item)
                        else:
                            new_images.append(data_item)
                    else:
                        exist_ratings.append(data_item)

        ImgLoader.execute_ratings(exist_ratings, q)
        ImgLoader.execute_svg_files(svg_files, q)
        ImgLoader.execute_exist_images(exist_images, q)
        ImgLoader.execute_new_images(new_images, q)
        ImgLoader.execute_stmt_list(stmt_list, conn)
    
    @staticmethod
    def execute_stmt_list(stmt_list: list, conn: Conn):
        for i in stmt_list:
            Dbase.execute(conn, i)
        Dbase.commit(conn)

    @staticmethod
    def execute_svg_files(data_items: list[DataItem], q: Queue):
        for i in data_items:
            img_array = ImgUtils.read_img(i.src)
            img_array = ImgUtils.resize(img_array, 512)
            i.img_array = img_array
            q.put(i)

    @staticmethod
    def execute_ratings(data_items: list[DataItem], q: Queue):
        for i in data_items:
            q.put(i)

    @staticmethod
    def execute_exist_images(data_items: list[DataItem], q: Queue):
        for i in data_items:
            img_array = Utils.read_thumb(i.thumb_path)
            i.img_array = img_array
            q.put(i)

    @staticmethod
    def execute_new_images(data_items: list[DataItem], q: Queue):
        for i in data_items:
            img_array = ImgUtils.read_img(i.src)
            img_array = ImgUtils.resize(img_array, Static.max_thumb_size)
            Utils.write_thumb(i.thumb_path, img_array)
            i.img_array = img_array
            q.put(i)

    @staticmethod
    def get_item_rating(data_item: DataItem, conn: Conn) -> bool:
        stmt = select(Clmns.rating)
        if data_item.type_ == Static.folder_type:
            stmt = stmt.where(*DataItem.get_folder_conds(data_item))
        else:
            stmt = stmt.where(Clmns.partial_hash==data_item.partial_hash)
        res = Dbase.execute(conn, stmt).scalar()
        return res
    

class ReadImg:
    @staticmethod
    def start(src: str, desaturate: bool, q: Queue):
        img_array = ImgUtils.read_img(src)
        if desaturate:
            img_array = Utils.desaturate_image(img_array, 0.2)
        q.put((src, img_array))


class _DirChangedHandler(FileSystemEventHandler):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def on_any_event(self, event):
        self.callback(event)


class DirWatcher:
    @staticmethod
    def start(path: str, q: Queue):
        if not path or not os.path.exists(path):
            return
        observer = Observer()
        handler = _DirChangedHandler(lambda e: q.put(e))
        observer.schedule(handler, path, recursive=False)
        observer.start()
        try:
            while True:
                sleep(1)
                if not os.path.exists(path):
                    break
        finally:
            observer.stop()
            observer.join()


class PathFixer:
    @staticmethod
    def start(path: str, q: Queue):
        if not path:
            result = (None, None)
        elif os.path.exists(path):
            result = (path, os.path.isdir(path))
        else:
            path_finder = PathFinder(path)
            fixed_path = path_finder.get_result()
            if fixed_path is not None:
                result = (fixed_path, os.path.isdir(fixed_path))
            else:
                result = (None, None)
        q.put(result)


class JpgConverter:
    @staticmethod
    def start(jpg_item: JpgConvertItem, q: Queue):
        jpg_item._urls = [i for i in jpg_item._urls if i.endswith(ImgUtils.ext_all)]
        jpg_item._urls.sort(key=lambda p: os.path.getsize(p))

        filename = ""
        new_urls: list[str] = []

        for count, url in enumerate(jpg_item._urls, start=1):
            save_path = JpgConverter._save_jpg(url)
            if save_path:
                new_urls.append(save_path)
                filename = os.path.basename(url)
                jpg_item.current_count = count
                jpg_item.current_filename = filename
                jpg_item.msg = ""
                q.put(jpg_item)

        jpg_item.msg = "finished"
        q.put(jpg_item)

    @staticmethod
    def _save_jpg(path: str) -> None:
        try:
            img_array = ImgUtils.read_img(path)
            img = Image.fromarray(img_array.astype(np.uint8))
            img = img.convert("RGB")
            save_path = os.path.splitext(path)[0] + ".jpg"
            img.save(save_path, format="JPEG", quality=99)
            return save_path
        except Exception:
            Utils.print_error()
            return None


class ImgRes:
    undef_text = "Неизвестно"
    @staticmethod
    def psd_read(path: str):
        try:
            w, h = ImgUtils.get_psd_size(path)
            resol= f"{w}x{h}"
        except Exception as e:
            print("multiprocess > ImgRes psd error", e)
            resol = ImgRes.undef_text
        return resol

    @staticmethod
    def read(path: str):
        img_ = ImgUtils.read_img(path)
        if img_ is not None and len(img_.shape) > 1:
            h, w = img_.shape[0], img_.shape[1]
            resol= f"{w}x{h}"
        else:
            resol = ImgRes.undef_text
        return resol

    @staticmethod
    def start(path: str, q: Queue):
        """
        Возвращает str "ширина изображения x высота изображения
        """
        if path.endswith(ImgUtils.ext_psd):
            resol = ImgRes.psd_read(path)
        else:
            resol = ImgRes.read(path)
        q.put(resol)


class MultipleInfo:
    err = " Произошла ошибка"

    @staticmethod
    def start(data_items: list[DataItem], show_hidden: bool, q: Queue):
        info_item = MultipleInfoItem()

        try:
            MultipleInfo._task(data_items, info_item, show_hidden)
            info_item.total_size = SharedUtils.get_f_size(info_item.total_size),
            info_item.total_files = len(list(info_item._files_set))
            info_item.total_files = format(info_item.total_files, ",").replace(",", " ")
            info_item.total_folders = len(list(info_item._folders_set))
            info_item.total_folders = format(info_item.total_folders, ",").replace(",", " ")
            q.put(info_item)

        except Exception as e:
            print("tasks, MultipleInfoFiles error", e)
            info_item.total_size = MultipleInfo.err
            info_item.total_files = MultipleInfo.err
            info_item.total_folders = MultipleInfo.err
            q.put(info_item)

    @staticmethod
    def _task(items: list[dict], info_item: MultipleInfoItem, show_hidden: bool):
        for i in items:
            if i["type_"] == Static.folder_type:
                MultipleInfo.get_folder_size(i, info_item, show_hidden)
                info_item._folders_set.add(i["src"])
            else:
                info_item.total_size += i["size"]
                info_item._files_set.add(i["src"])

    @staticmethod
    def get_folder_size(item: dict, info_item: MultipleInfoItem, show_hidden: bool):
        stack = [item["src"]]
        while stack:
            current_dir = stack.pop()
            try:
                os.listdir(current_dir)
            except Exception as e:
                print("tasks, MultipleItemsInfo error", e)
                continue
            for entry in os.scandir(current_dir):
                if entry.is_dir():
                    info_item._folders_set.add(item["src"])
                    stack.append(entry.path)
                else:
                    if show_hidden:
                        info_item.total_size += entry.stat().st_size
                        info_item._files_set.add(entry.path)
                    if not entry.name.startswith(Static.hidden_symbols):
                        info_item.total_size += entry.stat().st_size
                        info_item._files_set.add(entry.path)


class CopyWorker(BaseProcessWorker):
    def __init__(self, target, args):
        self.proc_q = Queue()
        self.gui_q = Queue()
        super().__init__(target, (*args, self.proc_q, self.gui_q))


class CopyTask:
    @staticmethod
    def start(copy_item: CopyItem, proc_q: Queue, gui_q: Queue):

        if copy_item.is_search or copy_item.src_dir != copy_item.dst_dir:
            src_dst_urls = CopyTask.get_another_dir_urls(copy_item)
        else:
            src_dst_urls = CopyTask.get_same_dir_urls(copy_item)

        copy_item.dst_urls = [dst for src, dst in src_dst_urls]

        total_size = 0
        for src, dest in src_dst_urls:
            total_size += os.path.getsize(src)

        copy_item.total_size = total_size // 1024
        copy_item.total_count = len(src_dst_urls)
        replace_all = False

        for count, (src, dest) in enumerate(src_dst_urls, start=1):

            if src.is_dir():
                continue

            if not replace_all and dest.exists() and src.name == dest.name:
                copy_item.msg = "need_replace"
                proc_q.put(copy_item)
                while True:
                    sleep(1)
                    if not gui_q.empty():
                        new_copy_item: CopyItem = gui_q.get()
                        if new_copy_item.msg == "replace_one":
                            break
                        elif new_copy_item.msg == "replace_all":
                            replace_all = True
                            break

            os.makedirs(dest.parent, exist_ok=True)
            copy_item.current_count = count
            copy_item.msg = ""
            try:
                if os.path.exists(dest) and dest.is_file():
                    os.remove(dest)
                CopyTask.copy_file_with_progress(proc_q, copy_item, src, dest)
            except Exception as e:
                print("CopyTask copy error", e)
                copy_item.msg = "error"
                proc_q.put(copy_item)
                return
            if copy_item.is_cut and not copy_item.is_search:
                os.remove(src)
                "удаляем файлы чтобы очистить директории"

        if copy_item.is_cut and not copy_item.is_search:
            for src, dst in src_dst_urls:
                if src.is_dir() and src.exists():
                    try:
                        shutil.rmtree(src)
                    except Exception as e:
                        print("copy task error dir remove", e)
        
        copy_item.msg = "finished"
        proc_q.put(copy_item)

    @staticmethod
    def get_another_dir_urls(copy_item: CopyItem):
        src_dst_urls: list[tuple[Path, Path]] = []
        src_dir = Path(copy_item.src_dir)
        dst_dir = Path(copy_item.dst_dir)
        for url in copy_item.src_urls:
            url = Path(url)
            if url.is_dir():
                # мы добавляем директорию в список копирования
                # чтобы потом можно было удалить ее при вырезании
                src_dst_urls.append((url, url))
                for filepath in url.rglob("*"):
                    if filepath.is_file():
                        rel_path = filepath.relative_to(src_dir)
                        new_path = dst_dir.joinpath(rel_path)
                        src_dst_urls.append((filepath, new_path))
            else:
                new_path = dst_dir.joinpath(url.name)
                src_dst_urls.append((url, new_path))
        return src_dst_urls
    
    @staticmethod
    def get_same_dir_urls(copy_item: CopyItem, copy_name: str = ""):
        src_dst_urls: list[tuple[Path, Path]] = []
        dst_dir = Path(copy_item.dst_dir)
        for url in copy_item.src_urls:
            url = Path(url)
            url_with_copy = dst_dir.joinpath(url.name)
            counter = 2
            while url_with_copy.exists():
                name, ext = os.path.splitext(url.name)
                new_name = f"{name} {copy_name} {counter}{ext}"
                url_with_copy = dst_dir.joinpath(new_name)
                counter += 1
            if url.is_file():
                src_dst_urls.append((url, url_with_copy))
            else:
                for filepath in url.rglob("*"):
                    if filepath.is_file():
                        rel_path = filepath.relative_to(url)
                        new_url = url_with_copy.joinpath(rel_path)
                        src_dst_urls.append((filepath, new_url))
        return src_dst_urls
    
    @staticmethod
    def copy_file_with_progress(proc_q: Queue, copy_item: CopyItem, src: Path, dest: Path):
        block = 4 * 1024 * 1024  # 4 MB
        with open(src, "rb") as fsrc, open(dest, "wb") as fdst:
            while True:
                buf = fsrc.read(block)
                if not buf:
                    break
                fdst.write(buf)
                copy_item.current_size += len(buf) // 1024
                proc_q.put(copy_item)
        shutil.copystat(src, dest, follow_symlinks=True)


class SearchTaskWorker(BaseProcessWorker):
    """
    - args: любые аргументы
    - proq_q, gui_q: передаются автоматически
    """
    def __init__(self, target, args):
        self.proc_q = Queue()
        self.gui_q = Queue()
        super().__init__(target, (*args, self.proc_q, self.gui_q))


class SearchTask:
    sleep_s = 0
    ratio = 0.85

    @staticmethod
    def start(search_item: SearchItem, proc_q: Queue, gui_q: Queue):
        engine = Dbase.create_engine()
        search_item.proc_q = proc_q
        search_item.gui_q = gui_q
        search_item.conn = Dbase.get_conn(engine)

        SearchTask.setup(search_item)

        SearchTask.scandir_recursive(search_item)
        Dbase.close_conn(search_item.conn)

    @staticmethod
    def setup(search_item: SearchItem):
        for i in search_item.search_list:
            search_item.search_list_low.append(i.lower())

    # базовый метод обработки os.DirEntry
    @staticmethod
    def process_entry(entry: os.DirEntry, search_item: SearchItem):
        for i in search_item.search_list_low:
            if i in entry.name.lower():
                return True
        return False
    
    @staticmethod
    def scandir_recursive(search_item: SearchItem):
        dirs_list = [search_item.root_dir, ]
        while dirs_list:
            current_dir = dirs_list.pop()
            if not os.path.exists(current_dir):
                continue
            try:
                # Сканируем текущий каталог и добавляем новые пути в стек
                SearchTask.scan_current_dir(current_dir, dirs_list, search_item)
            except OSError as e:
                Utils.print_error()
                continue
            except Exception as e:
                Utils.print_error()
                continue
    
    @staticmethod
    def scan_current_dir(current_dir: str, dir_list: list, search_item: SearchItem):
        for entry in os.scandir(current_dir):
            if entry.name.startswith(Static.hidden_symbols):
                continue
            if entry.is_dir():
                dir_list.append(entry.path)
            if SearchTask.process_entry(entry, search_item):
                SearchTask.process_img(entry, search_item)

    @staticmethod
    def process_img(entry: os.DirEntry, search_item: SearchItem):

        def execute_stmt_list(stmt_list: list):
            for i in stmt_list:
                Dbase.execute(search_item.conn, i)
            Dbase.commit(search_item.conn)

        def insert(data_item: DataItem, img_array: np.ndarray):
            if Utils.write_thumb(data_item.thumb_path, img_array):
                stmt_list.append(DataItem.insert_file_stmt(data_item))
                if len(stmt_list) == stmt_limit:
                    execute_stmt_list(stmt_list)
                    stmt_list.clear()

        stmt_list: list = []
        stmt_limit = 10

        data_item = DataItem(entry.path)
        data_item.set_properties()
        if data_item.type_ != Static.folder_type:
            data_item.set_partial_hash()
        if entry.name.endswith(ImgUtils.ext_all):
            if os.path.exists(data_item.thumb_path):
                img_array = Utils.read_thumb(data_item.thumb_path)
            else:
                img_array = ImgUtils.read_img(entry.path)
                img_array = ImgUtils.resize(img_array, Static.max_thumb_size)
                insert(data_item, img_array)
            data_item.img_array = img_array

        search_item.proc_q.put(data_item)
        sleep(SearchTask.sleep_s)
