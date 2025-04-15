import os
import re

import sqlalchemy
from PyQt5.QtGui import QPixmap
from sqlalchemy.exc import IntegrityError, OperationalError

from cfg import Dynamic, Static
from utils import Utils

METADATA = sqlalchemy.MetaData()
TABLE_NAME = "cache"
SQL_ERRORS = (OperationalError, IntegrityError)

class ColumnNames:
    ID = "id"
    IMG = "img"
    NAME = "name"
    TYPE = "type_"
    SIZE = "size"
    MOD = "mod"
    RATING = "rating"
    RESOL = "resol"
    CATALOG = "catalog"
    PARTIAL_HASH = "partial_hash"


CACHE = sqlalchemy.Table(
    TABLE_NAME, METADATA,
    # Комментарии колонок используются только для сортировки.
    # Где есть комментарий — сортировка возможна.
    sqlalchemy.Column(ColumnNames.ID, sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column(ColumnNames.IMG, sqlalchemy.BLOB),
    sqlalchemy.Column(ColumnNames.NAME, sqlalchemy.Text),
    sqlalchemy.Column(ColumnNames.TYPE, sqlalchemy.Text),
    sqlalchemy.Column(ColumnNames.SIZE, sqlalchemy.Integer),
    sqlalchemy.Column(ColumnNames.MOD, sqlalchemy.Integer),
    sqlalchemy.Column(ColumnNames.RATING, sqlalchemy.Integer),
    sqlalchemy.Column(ColumnNames.RESOL, sqlalchemy.Integer),
    sqlalchemy.Column(ColumnNames.CATALOG, sqlalchemy.Text),
    sqlalchemy.Column(ColumnNames.PARTIAL_HASH, sqlalchemy.Text)
)


# Служит для отображения типа сортировки
# Имя столбца базы данных соответствует параметру cfg.py > Dynamic.sort
# И текстовое отображение этого параметр
ORDER_DICT: dict[str, str] = {
    ColumnNames.NAME : "Имя",
    ColumnNames.TYPE : "Тип",
    ColumnNames.SIZE : "Размер",
    ColumnNames.MOD : "Дата изменения",
    ColumnNames.RATING : "Рейтинг",
}


class Dbase:

    def __init__(self):
        self.conn_count = 0
        self.conn_max = 3

    def create_engine(self, path: str) -> sqlalchemy.Engine | None:

        if self.conn_count == self.conn_max:
            return None
        
        elif os.path.isdir(path):
            print("Путь к БД должен быть файлом, а не папкой")
            return

        engine = sqlalchemy.create_engine(
            f"sqlite:///{path}",
            echo=False,
            connect_args={
                "check_same_thread": False,
                "timeout": 60
            }
        )

        try:
            # счетчик должен идти первым, потому что уже на инструкции
            # metadata.create_all уже может возникнуть ошибка

            self.conn_count += 1
            METADATA.create_all(bind=engine)
            conn = engine.connect()

            # проверяем доступность БД и соответствие таблицы
            q = sqlalchemy.select(CACHE)
            conn.execute(q).first()
            conn.close()

            return engine

        except SQL_ERRORS as e:
            # print(traceback.format_exc())
            print("create engine error", e)

            if os.path.exists(path):
                os.remove(path)

            self.create_engine(path=path)
