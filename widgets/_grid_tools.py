import os

import numpy as np
from sqlalchemy import Connection, insert, select, update
from sqlalchemy.exc import IntegrityError, OperationalError

from cfg import ThumbData
from database import CACHE, ColumnNames, OrderItem
from fit_img import FitImg
from utils import Utils

SQL_ERRORS = (IntegrityError, OperationalError)

        
class GridTools:

    @classmethod
    def update_order_item(cls, conn: Connection, order_item: OrderItem):

        try:
            return cls.update_order_item_(conn, order_item)

        except Exception as e:
            Utils.print_error(parent=cls, error=e)
            print(order_item.src)
            return None

    @classmethod
    def update_order_item_(cls, conn: Connection, order_item: OrderItem):
        
        db_item, rating = GridTools.load_db_item(
            conn=conn,
            order_item=order_item,
        )

        if isinstance(db_item, int):
            img_array = cls.update_db_item(
                conn=conn,
                order_item=order_item,
                row_id=db_item
            )

            # print("update")

        elif db_item is None:
            img_array = cls.insert_db_item(
                conn=conn,
                order_item=order_item
            )

            # print("insert")
        
        elif isinstance(db_item, bytes):
            img_array = Utils.bytes_to_array(
                blob=db_item
            )

            # print("already")

        if isinstance(img_array, np.ndarray):

            pixmap = Utils.pixmap_from_array(
                image=img_array
            )

            order_item.pixmap_ = pixmap
            order_item.rating = rating

            return order_item
        
        else:
            return None

    @classmethod
    def load_db_item(cls, conn: Connection, order_item: OrderItem):

        select_stmt = select(
            CACHE.c.id,
            CACHE.c.img,
            CACHE.c.size,
            CACHE.c.mod,
            CACHE.c.rating
        )

        where_stmt = select_stmt.where(
            CACHE.c.name == Utils.hash_filename(filename=order_item.name)
        )
        res_by_src = conn.execute(where_stmt).mappings().first()

        # Запись найдена
        if res_by_src:

            # даты изменения не совпадают, обновляем запись
            if res_by_src.get(ColumnNames.MOD) != order_item.mod:

                return (
                    res_by_src.get(ColumnNames.ID),
                    res_by_src.get(ColumnNames.RATING)
                )

            else:
                # даты изменения совпадают
                return (
                    res_by_src.get(ColumnNames.IMG),
                    res_by_src.get(ColumnNames.RATING)
                )

        # Запись по имени файла не найдена, возможно файл был переименован,
        # но содержимое файла не менялось
        # Пытаемся найти в БД запись по размеру и дате изменения order_item
        mod_stmt = select_stmt.where(CACHE.c.mod == order_item.mod)
        size_mod_stmt = mod_stmt.where(CACHE.c.size == order_item.size)
        size_mod_res = conn.execute(size_mod_stmt).mappings().first()

        # Если запись найдена, значит файл действительно был переименован
        # возвращаем ID для обновления записи
        if size_mod_res:
            return (
                size_mod_res.get(ColumnNames.ID),
                size_mod_res.get(ColumnNames.RATING)
            )

        # ничего не найдено, значит это будет новая запись и рейтинг 0
        return (None, 0)
    
    @classmethod
    def update_db_item(cls, conn: Connection, order_item: OrderItem, row_id: int) -> np.ndarray:

        bytes_img, img_array = cls.get_bytes_ndarray(
            order_item=order_item
        )

        new_size, new_mod, new_resol = cls.get_stats(
            order_item=order_item,
            img_array=img_array
        )

        new_name = Utils.hash_filename(filename=order_item.name)

        values = {
            ColumnNames.NAME: new_name,
            ColumnNames.IMG: bytes_img,
            ColumnNames.SIZE: new_size,
            ColumnNames.MOD: new_mod,
            ColumnNames.RESOL: new_resol
        }

        q = update(CACHE).where(CACHE.c.id == row_id)
        q = q.values(**values)

        # пытаемся вставить запись в БД, но если не выходит
        # все равно отдаем изображение
        cls.execute_query(conn=conn, query=q)

        return img_array

    @classmethod
    def insert_db_item(cls, conn: Connection, order_item: OrderItem) -> np.ndarray:

        bytes_img, img_array = cls.get_bytes_ndarray(
            order_item=order_item
        )

        new_size, new_mod, new_resol = cls.get_stats(
            order_item=order_item,
            img_array=img_array
        )

        new_name = Utils.hash_filename(filename=order_item.name)

        values = {
            ColumnNames.IMG: bytes_img,
            ColumnNames.NAME: new_name,
            ColumnNames.TYPE: order_item.type_,
            ColumnNames.SIZE: new_size,
            ColumnNames.MOD: new_mod,
            ColumnNames.RATING: 0,
            ColumnNames.RESOL: new_resol,
            ColumnNames.CATALOG: ""
        }

        q = insert(CACHE)
        q = q.values(**values)

        # пытаемся вставить запись в БД, но если не выходит
        # все равно отдаем изображение
        cls.execute_query(conn=conn, query=q)
        return img_array
    
    @classmethod
    def get_bytes_ndarray(cls, order_item: OrderItem):

        img_array = Utils.read_image(
            path=order_item.src
        )

        img_array = FitImg.start(
            image=img_array,
            size=ThumbData.DB_PIXMAP_SIZE
        )

        bytes_img = Utils.numpy_to_bytes(
            img_array=img_array
        )

        return bytes_img, img_array
    
    @classmethod
    def get_stats(cls, order_item: OrderItem, img_array: np.ndarray):

        stats = os.stat(order_item.src)
        height, width = img_array.shape[:2]

        new_size = int(stats.st_size)
        new_mod = int(stats.st_mtime)
        new_resol = f"{width}x{height}"

        return new_size, new_mod, new_resol
    
    @classmethod
    def execute_query(cls, conn: Connection, query):
        try:
            conn.execute(query)
            conn.commit()
        except SQL_ERRORS as e:
            Utils.print_error(parent=cls, error=e)
            conn.rollback()