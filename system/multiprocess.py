import os
from multiprocessing import Process, Queue

import numpy as np
from database import Clmns, Dbase
from shared_utils import ReadImage, SharedUtils
from sqlalchemy import Connection as Conn
from sqlalchemy import select

from cfg import JsonData, Static
from system.items import DataItem, MainWinItem, SortItem
from system.shared_utils import PathFinder
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
        # Запускаем процесс
        self.proc.start()

    def force_stop(self):
        # Принудительно останавливаем процесс, если он ещё жив
        if self.proc.is_alive():
            self.proc.terminate()  # посылаем сигнал terminate
            self.proc.join()       # ждём завершения процесса

        # Закрываем очередь и дожидаемся завершения её внутреннего потока
        if self.queue:
            self.queue.close()
            self.queue.join_thread()

    def get_queue(self):
        # Возвращает очередь для чтения данных из процесса
        return self.queue

    def close(self):
        # Корректно закрываем очередь
        if self.queue:
            self.queue.close()
            self.queue.join_thread()

        # Если процесс уже завершён, выполняем join для очистки ресурсов
        if self.proc and not self.proc.is_alive():
            self.proc.join()


class FinderItemsLoader:
    @staticmethod
    def start(main_win_item: MainWinItem, sort_item: SortItem, out_q: Queue):
        items = []
        hidden_syms = () if JsonData.show_hidden else Static.hidden_symbols

        fixed_path = PathFinder(main_win_item.main_dir).get_result()
        if fixed_path is None:
            out_q.put({"path": None, "data_items": []})
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
        out_q.put({"path": fixed_path, "data_items": items})


class DbItemsLoader:
    """
    Короче тебе надо на лету во время циклов обновлять очередь Queue
    И в гуишке написать метод, который будет принимать очередь
    и раскидывать че делать: устанавливать ли рейтинг или устанавливать картинку
    """

    @staticmethod
    def start(self, data_items: list[DataItem], q: Queue):
        data_items.sort(key=lambda x: x.size)

        conn = Dbase.get_conn(Dbase.engine)
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
                rating = DbItemsLoader.get_item_rating(data_item)
                if rating is None:
                    stmt_list.append(DataItem.insert_folder_stmt(data_item))
                else:
                    data_item.rating = rating
                    stmt_list.append(DataItem.update_folder_stmt(data_item))
                    exist_ratings.append(data_item)
            else:
                data_item.set_partial_hash()
                rating = self.get_item_rating(data_item)
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

        DbItemsLoader.execute_ratings(exist_ratings)

        svg_files = DbItemsLoader.execute_svg_files(svg_files)
        DbItemsLoader.execute_exist_images(exist_images)
        DbItemsLoader.execute_new_images(new_images)
        DbItemsLoader.execute_stmt_list(stmt_list)
        DbItemsLoader.execute_corrupted_images()
    
    @staticmethod
    def execute_stmt_list(stmt_list: list, conn: Conn):
        for i in stmt_list:
            Dbase.execute(conn, i)
        Dbase.commit(conn)

    @staticmethod
    def execute_svg_files(data_items: list[DataItem], q: Queue):
        for i in data_items:
            img_array = "загружаем свг как аррай"
            i.arrays = {
                sz: {img_array, "МЕТОД ДЛЯ РЕСАЙЗА"}
                for sz in Static.image_sizes
            }
            i.arrays.update(
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
            i.arrays = {
                sz: {img_array, "МЕТОД ДЛЯ РЕСАЙЗА"}
                for sz in Static.image_sizes
            }
            i.arrays.update(
                {"src": img_array}
            )
            q.put(i)

    @staticmethod
    def execute_new_images(data_items: list[DataItem], q: Queue):
        for i in data_items:

            "ПОСЫЛАЕМ СИГНАЛ, ЧТОБЫ THUMB В СЕТКЕ СТАЛ ПОЛУПРОЗРАЧНЫМ"
            "например обработчик будет считывать флаг set_loading"
            q.put({"set_loading": i})

            img_array = ReadImage.read_image(i.src)
            img_array = SharedUtils.fit_image(img_array, Static.max_thumb_size)
            i.arrays = {
                sz: {img_array, "МЕТОД ДЛЯ РЕСАЙЗА"}
                for sz in Static.image_sizes
            }
            i.arrays.update(
                {"src": img_array}
            )
            Utils.write_thumb(i.thumb_path, img_array)
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