import os
import shutil
from multiprocessing import Process, Queue
from pathlib import Path
from time import sleep

import numpy as np
import sqlalchemy
from PIL import Image
from sqlalchemy import Connection as Conn
from sqlalchemy import select
from watchdog.events import FileSystemEventHandler
from watchdog.observers.polling import PollingObserver as Observer

from cfg import JsonData, Static
from system.database import Clmns, Dbase
from system.items import CopyItem, DataItem, MainWinItem, SortItem
from system.shared_utils import PathFinder, ReadImage, SharedUtils
from system.tasks import Utils


class ProcessWorker:
    def __init__(self, target: callable, args: tuple):
        # Создаём очередь для передачи данных из процесса в GUI
        self.queue = Queue()
        # Создаём процесс, который будет выполнять target(*args, queue)
        self.proc = Process(
            target=target,
            args=(*args, self.queue)
        )

    def start(self):
        try:
            self.proc.start()
        except Exception as e:
            print("process worker error", e)

    def get_queue(self):
        # Возвращает очередь для чтения данных из процесса
        return self.queue
    
    def terminate(self):
        self.proc.terminate()
        self.proc.join(timeout=0.2)

        self.queue.close()
        self.queue.join_thread()


class FinderItemsLoader:
    @staticmethod
    def start(main_win_item: MainWinItem, sort_item: SortItem, show_hidden: bool, q: Queue):
        """
        Добавляет в очередь {"path": str filepath, "data_items": list DataItem}
        """
        items = []
        hidden_syms = () if show_hidden else Static.hidden_symbols

        fixed_path = PathFinder(main_win_item.main_dir).get_result()
        if fixed_path is None:
            q.put({"path": None, "data_items": []})
            return

        for entry in os.scandir(fixed_path):
            if entry.name.startswith(hidden_syms):
                continue
            if not os.access(entry.path, 4):
                continue

            item = DataItem(entry.path)
            item.set_properties()
            items.append(item)

        items = DataItem.sort_(items, sort_item)
        q.put({"path": fixed_path, "data_items": items})


class DbItemsLoader:

    """
    {"src": filepath , "img_array": numpy ndarray with Static.max_thumb_size}
    """
    
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
                rating = DbItemsLoader.get_item_rating(data_item, conn)
                if rating is None:
                    stmt_list.append(DataItem.insert_folder_stmt(data_item))
                else:
                    data_item.rating = rating
                    stmt_list.append(DataItem.update_folder_stmt(data_item))
                    exist_ratings.append(data_item)
            else:
                data_item.set_partial_hash()
                rating = DbItemsLoader.get_item_rating(data_item, conn)
                if rating is None:
                    stmt_list.append(DataItem.insert_file_stmt(data_item))
                    if data_item.type_ in Static.img_exts:
                        new_images.append(data_item)
                else:
                    data_item.rating = rating
                    stmt_list.append(DataItem.update_file_stmt(data_item))
                    if data_item.type_ in Static.img_exts:
                        if data_item.thumb_path and os.path.exists(data_item.thumb_path):
                            exist_images.append(data_item)
                        else:
                            new_images.append(data_item)
                    else:
                        exist_ratings.append(data_item)

        DbItemsLoader.execute_ratings(exist_ratings, q)
        DbItemsLoader.execute_svg_files(svg_files, q)
        DbItemsLoader.execute_exist_images(exist_images, q)
        DbItemsLoader.execute_new_images(new_images, q)
        DbItemsLoader.execute_stmt_list(stmt_list, conn)
    
    @staticmethod
    def execute_stmt_list(stmt_list: list, conn: Conn):
        for i in stmt_list:
            Dbase.execute(conn, i)
        Dbase.commit(conn)

    @staticmethod
    def execute_svg_files(data_items: list[DataItem], q: Queue):
        for i in data_items:
            img_array = ReadImage.read_image(i.src)
            img_array = SharedUtils.fit_image(img_array, 512)
            data = {"src": i.src, "img_array": img_array}
            q.put(data)

    @staticmethod
    def execute_ratings(data_items: list[DataItem], q: Queue):
        for i in data_items:
            q.put(i)

    @staticmethod
    def execute_exist_images(data_items: list[DataItem], q: Queue):
        for i in data_items:
            img_array = Utils.read_thumb(i.thumb_path)
            data = {"src": i.src, "img_array": img_array}
            q.put(data)

    @staticmethod
    def execute_new_images(data_items: list[DataItem], q: Queue):
        for i in data_items:
            img_array = ReadImage.read_image(i.src)
            img_array = SharedUtils.fit_image(img_array, Static.max_thumb_size)
            Utils.write_thumb(i.thumb_path, img_array)
            data = {"src": i.src, "img_array": img_array}
            q.put(data)

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

    cache_limit = 15

    @staticmethod
    def start(src: str, desaturate: bool, q: Queue):
        """
        nd array or none
        """
        img_array = ReadImage.read_image(src)
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


class ToJpegConverter:

    @staticmethod
    def start(urls: list[str], q: Queue):
        """
        Возвращает {
            "total_count": int,
            "count": int,
            "filename": str
        }
        """

        urls = [i for i in urls if i.endswith(Static.img_exts)]
        urls.sort(key=lambda p: os.path.getsize(p))

        count = 0
        filename = ""
        new_urls: list[str] = []

        for x, url in enumerate(urls, start=1):
            save_path = ToJpegConverter._save_jpg(url)
            if save_path:
                new_urls.append(save_path)
                count = x
                filename = os.path.basename(url)

                q.put({
                    "total_count": len(urls),
                    "count": count,
                    "filename": filename
                })

    @staticmethod
    def _save_jpg(path: str) -> None:
        try:
            img_array = ReadImage.read_image(path)
            img = Image.fromarray(img_array.astype(np.uint8))
            img = img.convert("RGB")
            save_path = os.path.splitext(path)[0] + ".jpg"
            img.save(save_path, format="JPEG", quality=99)
            return save_path
        except Exception:
            Utils.print_error()
            return None
        


class CacheDownloader:

    @staticmethod
    def start(dirs: list[str], q: Queue):
        """
        Возвращает {
            "total_count": int,
            "count": int,
            "filename": str
        }
        """

        engine = Dbase.create_engine()
        conn = Dbase.get_conn(engine)
        new_images = CacheDownloader.prepare_images(conn, dirs)
        total_count = len(new_images)
        stmt_limit = 10
        count = 0
        filename = ""
        stmt_list = []

        for x, data in enumerate(new_images, start=1):
            data_item: DataItem = data["data_item"]
            count = x
            filename = data_item.filename
            if CacheDownloader.write_thumb(data_item):
                stmt_list.append(data["stmt"])
                q.put({
                    "total_count": total_count,
                    "count": count,
                    "filename": filename
                })
                if len(stmt_list) == stmt_limit:
                    CacheDownloader.execute_stmt_list(conn, stmt_list)
                    stmt_list.clear()

        if stmt_list:
            CacheDownloader.execute_stmt_list(conn, stmt_list)

    @staticmethod
    def execute_stmt_list(conn: sqlalchemy.Connection, stmt_list: list):
        for i in stmt_list:
            Dbase.execute(conn, i)
        Dbase.commit(conn)

    @staticmethod
    def prepare_images(conn: sqlalchemy.Connection, dirs: list[str]):
        new_images: list[dict[DataItem, str]] = []
        stack = [*dirs]

        while stack:
            last_dir = stack.pop()
            for i in os.scandir(last_dir):
                if i.is_dir():
                    stack.append(i.path)
                elif i.name.endswith(Static.img_exts):
                    data_item = DataItem(i.path)
                    data_item.set_properties()
                    data_item.set_partial_hash()
                    if CacheDownloader.exists_check(conn, data_item) is None:
                        new_images.append({
                            "data_item": data_item,
                            "stmt": DataItem.insert_file_stmt(data_item)
                        })
        return new_images

    @staticmethod
    def exists_check(conn: sqlalchemy.Connection, data_item: DataItem):
        stmt = (
            sqlalchemy.select(Clmns.id)
            .where(Clmns.partial_hash == data_item.partial_hash)
        )
        return Dbase.execute(conn, stmt).scalar() or None
    
    @staticmethod
    def cut_filename(text: str, limit: int = 25):
        if len(text) > limit:
            return text[:limit] + "..."
        return text

    @staticmethod
    def write_thumb(data_item: DataItem):
        img = ReadImage.read_image(data_item.src)
        img = SharedUtils.fit_image(img, Static.max_thumb_size)
        return Utils.write_thumb(data_item.thumb_path, img)
    

class ImgRes:

    undef_text = "Неизвестно"

    def start(path: str, q: Queue):
        """
        Возвращает str "ширина изображения x высота изображения
        """
        img_ = ReadImage.read_image(path)
        if img_ is not None and len(img_.shape) > 1:
            h, w = img_.shape[0], img_.shape[1]
            resol= f"{w}x{h}"
        else:
            resol = ImgRes.undef_text
        q.put(resol)


class _MultipleInfoItem:
    def __init__(self):
        super().__init__()
        self.total_size: int = 0
        self.folders_set = set()
        self.files_set = set()


class MultipleInfo:
    err = " Произошла ошибка"

    @staticmethod
    def start(data_items: list[DataItem], show_hidden: bool, q: Queue):
        """
        Принимает [
            "src": str,
            "type_": str,
            "size": int
        ]
        Возвращает {
            "total_size": str,
            "total_files": str,
            "total_folders": str
        }
        """

        info_item = _MultipleInfoItem()
        try:
            MultipleInfo._task(data_items, info_item, show_hidden)
            total_files = len(list(info_item.files_set))
            total_folders = len(list(info_item.folders_set))
            
            q.put({
                "total_size": SharedUtils.get_f_size(info_item.total_size),
                "total_files": format(total_files, ",").replace(",", " "),
                "total_folders": format(total_folders, ",").replace(",", " ")
            })
        except Exception as e:
            print("tasks, MultipleInfoFiles error", e)
            import traceback
            print(traceback.format_exc())
            q.put({
                "total_size": MultipleInfo.err,
                "total_files": MultipleInfo.err,
                "total_folders": MultipleInfo.err
            })

    @staticmethod
    def _task(items: list[dict], info_item: _MultipleInfoItem, show_hidden: bool):
        for i in items:
            if i["type_"] == Static.folder_type:
                MultipleInfo.get_folder_size(i, info_item, show_hidden)
                info_item.folders_set.add(i["src"])
            else:
                info_item.total_size += i["size"]
                info_item.files_set.add(i["src"])

    @staticmethod
    def get_folder_size(item: dict, info_item: _MultipleInfoItem, show_hidden: bool):
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
                    info_item.folders_set.add(item["src"])
                    stack.append(entry.path)
                else:
                    if show_hidden:
                        info_item.total_size += entry.stat().st_size
                        info_item.files_set.add(entry.path)
                    if not entry.name.startswith(Static.hidden_symbols):
                        info_item.total_size += entry.stat().st_size
                        info_item.files_set.add(entry.path)


class CopyFilesTask:

    @staticmethod
    def start(copy_item: CopyItem):
        src_dst_urls: list[tuple[Path, Path]] = []
        if copy_item.is_search or copy_item.dst_dir != copy_item.src_dir:
            src_dst_urls.extend(CopyFilesTask.get_another_dir_urls(copy_item))
        else:
            src_dst_urls.extend(CopyFilesTask.get_same_dir_urls(copy_item))

        for src, dst in src_dst_urls:
            # if src.is_dir() or dst.is_dir():
                print(dst)

        for src, dest in src_dst_urls:
            copy_item.total_size += os.path.getsize(src)
        copy_item.total_count = len(src_dst_urls)

        # for i in copy_item.src_dst_urls:
        #     print(i)

        # self.sigs.total_size.emit(self.total_size // 1024)

        # for count, (src, dest) in enumerate(self.src_dest_list, start=1):
        #     if not self.is_should_run():
        #         break
        #     os.makedirs(os.path.dirname(dest), exist_ok=True)
        #     self.copied_count = count
        #     try:
        #         self.copy_file_with_progress(src, dest)
        #     except Exception as e:
        #         Utils.print_error()
        #         self.sigs.error_win.emit()
        #         break
        #     if CopyItem.get_is_cut() and not CopyItem.get_is_search():
        #         os.remove(src)

        # if CopyItem.get_is_cut() and not CopyItem.get_is_search():
        #     for i in CopyItem.urls:
        #         if os.path.isdir(i):
        #             shutil.rmtree(i)

        # self.sigs.finished_.emit(self.paths)

    @staticmethod
    def get_another_dir_urls(copy_item: CopyItem):
        src_dst_urls: list[tuple[Path, Path]] = []
        src_dir = Path(copy_item.src_dir)
        dst_dir = Path(copy_item.dst_dir)
        for url in copy_item.urls:
            url = Path(url)
            if url.is_dir():
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
    def get_same_dir_urls(copy_item: CopyItem):
        src_dst_urls: list[tuple[Path, Path]] = []
        dst_dir = Path(copy_item.dst_dir)
        for url in copy_item.urls:
            url = Path(url)
            url_with_copy = dst_dir.joinpath(url.name)
            counter = 1
            while url_with_copy.exists():
                name, ext = os.path.splitext(url.name)
                new_name = f"{name} — копия {counter}{ext}"
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
    
    def copy_file_with_progress(self, src, dest):
        block = 4 * 1024 * 1024  # 4 MB
        with open(src, "rb") as fsrc, open(dest, "wb") as fdst:
            while True:
                buf = fsrc.read(block)
                if not buf:
                    break
                fdst.write(buf)
                self.copied_size += len(buf) // 1024

        shutil.copystat(src, dest, follow_symlinks=True)