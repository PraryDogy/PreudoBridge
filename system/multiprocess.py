import os
from multiprocessing import Process, Queue
from time import sleep

import numpy as np
from sqlalchemy import Connection as Conn
from sqlalchemy import Engine, select
from watchdog.events import FileSystemEventHandler
from watchdog.observers.polling import PollingObserver as Observer

from cfg import JsonData, Static
from system.database import Clmns, Dbase
from system.items import DataItem, MainWinItem, SortItem
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


class FinderItemsLoader:
    @staticmethod
    def start(main_win_item: MainWinItem, sort_item: SortItem, q: Queue):
        """
        q передается автоматически из ProcessWorker
        """
        items = []
        hidden_syms = () if JsonData.show_hidden else Static.hidden_symbols

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
        """
        q передается автоматически из ProcessWorker
        Отправляет в Queue DataItem или {"DataItem": DataItem}
        """

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
        # DbItemsLoader.execute_svg_files(svg_files)
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
            img_array = "загружаем свг как аррай"
            i.img_array = {
                sz: SharedUtils.fit_image(img_array, sz)
                for sz in Static.image_sizes
            }
            i.img_array.update(
                {"src": img_array}
            )
            q.put(i)

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
        if not path:
            return

        observer = Observer()
        handler = _DirChangedHandler(lambda e: q.put(e))
        observer.schedule(handler, path, recursive=False)
        observer.start()

        try:
            while True:
                sleep(1)
                print("dirs watcer", path)
        finally:
            observer.stop()
            observer.join()