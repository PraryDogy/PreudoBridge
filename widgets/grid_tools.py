import os

import numpy as np
from PyQt5.QtGui import QPixmap
from sqlalchemy import Connection, insert, select, update
from sqlalchemy.exc import IntegrityError, OperationalError

from cfg import Dynamic, Static, ThumbData
from database import CACHE, ColumnNames
from fit_img import FitImg
from utils import Utils

from .grid import Thumb

SQL_ERRORS = (IntegrityError, OperationalError)


class Tools:
    @classmethod
    def commit_(cls, conn: Connection, query):
        Dynamic.busy_db = True
        try:
            conn.execute(query)
            conn.commit()
        except SQL_ERRORS as e:
            Utils.print_error(parent=cls, error=e)
            conn.rollback()
        Dynamic.busy_db = False


class AnyBaseItem:

    @classmethod
    def load_db_record(cls, conn: Connection, base_item: Thumb):
        """
        Проверяет, есть ли запись в базе данных об этом Thumb по имени.    
        Если записи нет, делает запись.
        Thumb: любой файл, кроме файлов изображений и папок.
        """
        if not cls.load_from_db(conn, base_item):
            cls.insert_new_record(conn, base_item)
        return base_item        

    @classmethod
    def load_from_db(cls, conn: Connection, base_item: Thumb):
        """
        Загружает id записи (столбец не принципиален) с условием по имени.  
        Возвращает True если запись есть, иначе False.
        """
        select_stmt = select(CACHE.c.id)
        where_stmt = select_stmt.where(CACHE.c.name == Utils.get_hash_filename(base_item.name))
        res_by_src = conn.execute(where_stmt).mappings().first()
        if res_by_src:
            return True
        else:
            return False

    @classmethod
    def insert_new_record(cls, conn: Connection, base_item: Thumb):
        """
        Новая запись в базу данных.
        """
        new_name = Utils.get_hash_filename(filename=base_item.name)

        values = {
            ColumnNames.NAME: new_name,
            ColumnNames.TYPE: base_item.type_,
            ColumnNames.RATING: 0,
        }

        q = insert(CACHE).values(**values)
        Tools.commit_(conn, q)


class ImageBaseItem:

    @classmethod
    def load_db_record(cls, conn: Connection, base_item: Thumb) -> QPixmap | None:

        img_array = None
        Dynamic.busy_db = True
        img_array = cls.check_db_record(conn, base_item)
        Dynamic.busy_db = False
        if isinstance(img_array, np.ndarray):
            pixmap = Utils.pixmap_from_array(image=img_array)
            base_item.set_pixmap_storage(pixmap)
            return base_item
        else:
            return None

    @classmethod
    def check_db_record(cls, conn: Connection, base_item: Thumb) -> np.ndarray | None:
        """
        Загружает данные о Thumb из базы данных.
        """

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

        if res_by_name:
            if res_by_name.get(ColumnNames.MOD) != base_item.mod:
                return cls.update_db_record(conn, base_item, res_by_name.get(ColumnNames.ID))
            else:
                return None
        else:
            return cls.insert_db_record(conn, base_item)
    
    @classmethod
    def update_db_record(cls, conn: Connection, base_item: Thumb, row_id: int) -> np.ndarray:
        """
        Обновляет запись в базе данных:     
        имя, изображение bytes, размер, дата изменения, разрешение, хеш 10мб
        """
        img_array = cls.get_small_ndarray_img(base_item.src)
        bytes_img = Utils.numpy_to_bytes(img_array)
        new_size, new_mod, new_resol = cls.get_stats(base_item.src, img_array)
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
        q = update(CACHE).where(CACHE.c.id == row_id)
        q = q.values(**values)
        Tools.commit_(conn, q)
        return img_array

    @classmethod
    def insert_db_record(cls, conn: Connection, base_item: Thumb) -> np.ndarray:
        img_array = cls.get_small_ndarray_img(base_item.src)
        bytes_img = Utils.numpy_to_bytes(img_array)
        new_size, new_mod, new_resol = cls.get_stats(base_item.src, img_array)
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
        q = insert(CACHE).values(**values)
        Tools.commit_(conn, q)
        return img_array
    
    @classmethod
    def get_small_ndarray_img(cls, src: str) -> np.ndarray:
        img_array_src = Utils.read_image(src)
        img_array = FitImg.start(img_array_src, ThumbData.DB_IMAGE_SIZE)
        img_array_src = None
        del img_array_src
        return img_array
    
    @classmethod
    def get_stats(cls, src: str, img_array: np.ndarray):
        """
        Возвращает: размер, дату изменения, разрешение
        """
        stats = os.stat(src)
        height, width = img_array.shape[:2]
        new_size = int(stats.st_size)
        new_mod = int(stats.st_mtime)
        new_resol = f"{width}x{height}"
        return new_size, new_mod, new_resol
    

class GridTools:

    @classmethod
    def check_db_record(cls, conn: Connection, base_item: Thumb):
        """
        Если Thumb является папкой или любым файлом, кроме изображений,     
        то проверяет наличие в базе данных, если записи нет, делает запись  
        в базу данных об объекте.   
        Если Thumb является изображением, то сверяет Thumb с базой данных,  
        создает / обновляет запись.
        """
        try:
            if base_item.type_ not in Static.IMG_EXT:
                item = ImageBaseItem.load_db_record(conn, base_item)
            else:
                item = AnyBaseItem.load_db_record(conn, base_item)
            return item
        except Exception as e:
            return None
