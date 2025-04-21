import os

import numpy as np
from sqlalchemy import Connection, insert, select, update
from sqlalchemy.exc import IntegrityError, OperationalError

from cfg import Dynamic, Static, ThumbData
from database import CACHE, ColumnNames
from fit_img import FitImg
from utils import Utils

from .grid import Thumb

SQL_ERRORS = (IntegrityError, OperationalError)


class CommitTool:
    @classmethod
    def run(cls, conn: Connection, query):
        Dynamic.busy_db = True
        try:
            conn.execute(query)
            conn.commit()
        except SQL_ERRORS as e:
            Utils.print_error(parent=cls, error=e)
            conn.rollback()
        Dynamic.busy_db = False


class AnyBaseItem(CommitTool):

    @classmethod
    def update_any_base_item(cls, conn: Connection, base_item: Thumb):
        already_in_db = cls.load_base_item(conn, base_item)
        if not already_in_db:
            cls.insert_base_item(conn, base_item)
        return base_item        

    @classmethod
    def load_base_item(cls, conn: Connection, base_item: Thumb):
        select_stmt = select(CACHE.c.rating)
        where_stmt = select_stmt.where(CACHE.c.name == Utils.get_hash_filename(base_item.name))
        res_by_src = conn.execute(where_stmt).mappings().first()
        if res_by_src:
            return True
        else:
            return False

    @classmethod
    def insert_base_item(cls, conn: Connection, base_item: Thumb):

        new_name = Utils.get_hash_filename(filename=base_item.name)

        values = {
            ColumnNames.NAME: new_name,
            ColumnNames.TYPE: base_item.type_,
            ColumnNames.RATING: 0,
        }

        q = insert(CACHE).values(**values)
        cls.run(conn=conn, query=q)

    @classmethod
    def update_thumb(cls, conn: Connection, base_item: Thumb):

        new_name = Utils.get_hash_filename(filename=base_item.name)

        values = {
            ColumnNames.NAME: new_name,
            ColumnNames.TYPE: base_item.type_,
            ColumnNames.RATING: 0,
        }

        q = update(CACHE).values(**values).where(CACHE.c.name == new_name)
        cls.run(conn=conn, query=q)


class GridTools(AnyBaseItem):

    @classmethod
    def update_thumb(cls, conn: Connection, base_item: Thumb):

        try:
            if base_item.type_ == Static.FOLDER_TYPE:
                item = cls.update_any_base_item(conn, base_item)
            elif base_item.type_ in Static.IMG_EXT:
                item = cls.update_file_base_item(conn, base_item)
            else:
                item = cls.update_any_base_item(conn, base_item)

            return item
        except Exception as e:
            # import traceback
            # print(traceback.format_exc())
            # print("grid tools", e)
            return None

    @classmethod
    def update_file_base_item(cls, conn: Connection, base_item: Thumb):

        # ошибка логики в том, что мы пытаемся загрузить запись
        # которой еще нет в БД (загрузка по имени)
        # и тогда происходит загрузка по "дата изменения + размер"
        # а дата изменения и размер могут быть одинаковыми у нескольких
        # записей
        
        img_array = None

        Dynamic.busy_db = True
        db_item, rating = GridTools.load_file(
            conn=conn,
            base_item=base_item,
        )
        Dynamic.busy_db = False

        if isinstance(db_item, int):
            img_array = cls.update_file(
                conn=conn,
                base_item=base_item,
                row_id=db_item
            )

            # print("update")

        elif db_item is None:
            img_array = cls.insert_file(conn=conn, base_item=base_item)

            # print("insert")
        
        elif isinstance(db_item, bytes):
            img_array = Utils.bytes_to_array(blob=db_item)

            # print("already")

        if isinstance(img_array, np.ndarray):
            pixmap = Utils.pixmap_from_array(image=img_array)

            base_item.set_pixmap_storage(pixmap)
            base_item.rating = rating

            return base_item
        
        else:
            return None

    @classmethod
    def load_file(cls, conn: Connection, base_item: Thumb):

        select_stmt = select(
            CACHE.c.id,
            CACHE.c.img,
            CACHE.c.size,
            CACHE.c.mod,
            CACHE.c.rating
        )

        where_stmt = select_stmt.where(
            CACHE.c.name == Utils.get_hash_filename(filename=base_item.name)
        )
        res_by_name = conn.execute(where_stmt).mappings().first()

        # Запись по имени файла найдена 
        # Нужна проверка именно по хеш-имени, а не по хеш-содержимому,
        # чтобы не пришлось открывать каждый файл для проверки 
        if res_by_name:

            # даты изменения не совпадают, обновляем запись
            if res_by_name.get(ColumnNames.MOD) != base_item.mod:
                return (
                    res_by_name.get(ColumnNames.ID),
                    res_by_name.get(ColumnNames.RATING)
                )

            else:
                # даты изменения совпадают
                return (
                    res_by_name.get(ColumnNames.IMG),
                    res_by_name.get(ColumnNames.RATING)
                )

        else:
            return (None, 0)
    
    @classmethod
    def update_file(
        cls, conn: Connection, base_item: Thumb, row_id: int,
        rating: int = None
        ) -> np.ndarray:

        bytes_img, img_array = cls.get_bytes_ndarray(
            base_item=base_item
        )

        new_size, new_mod, new_resol = cls.get_stats(
            base_item=base_item,
            img_array=img_array
        )

        new_name = Utils.get_hash_filename(filename=base_item.name)
        partial_hash = Utils.get_partial_hash(file_path=base_item.src)

        values = {
            ColumnNames.NAME: new_name,
            ColumnNames.IMG: bytes_img,
            ColumnNames.SIZE: new_size,
            ColumnNames.MOD: new_mod,
            ColumnNames.RESOL: new_resol,
            ColumnNames.PARTIAL_HASH: partial_hash
        }

        if rating:
            values[ColumnNames.RATING] = rating

        q = update(CACHE).where(CACHE.c.id == row_id)
        q = q.values(**values)

        # пытаемся вставить запись в БД, но если не выходит
        # все равно отдаем изображение
        cls.run(conn=conn, query=q)

        return img_array

    @classmethod
    def insert_file(
        cls, conn: Connection, base_item: Thumb,
        rating: int = None
        ) -> np.ndarray:

        bytes_img, img_array = cls.get_bytes_ndarray(
            base_item=base_item
        )

        new_size, new_mod, new_resol = cls.get_stats(
            base_item=base_item,
            img_array=img_array
        )

        new_name = Utils.get_hash_filename(filename=base_item.name)
        partial_hash = Utils.get_partial_hash(file_path=base_item.src)

        values = {
            ColumnNames.IMG: bytes_img,
            ColumnNames.NAME: new_name,
            ColumnNames.TYPE: base_item.type_,
            ColumnNames.SIZE: new_size,
            ColumnNames.MOD: new_mod,
            ColumnNames.RATING: 0,
            ColumnNames.RESOL: new_resol,
            ColumnNames.CATALOG: "",
            ColumnNames.PARTIAL_HASH: partial_hash
        }

        if rating:
            values[ColumnNames.RATING] = rating

        q = insert(CACHE)
        q = q.values(**values)

        # пытаемся вставить запись в БД, но если не выходит
        # все равно отдаем изображение
        cls.run(conn=conn, query=q)

        return img_array
    
    @classmethod
    def get_bytes_ndarray(cls, base_item: Thumb):

        img_array_src = Utils.read_image(
            path=base_item.src
        )

        img_array = FitImg.start(
            image=img_array_src,
            size=ThumbData.DB_IMAGE_SIZE
        )

        img_array_src = None
        del img_array_src
        # gc.collect()

        bytes_img = Utils.numpy_to_bytes(
            img_array=img_array
        )

        return bytes_img, img_array
    
    @classmethod
    def get_stats(cls, base_item: Thumb, img_array: np.ndarray):

        stats = os.stat(base_item.src)
        height, width = img_array.shape[:2]

        new_size = int(stats.st_size)
        new_mod = int(stats.st_mtime)
        new_resol = f"{width}x{height}"

        return new_size, new_mod, new_resol
    