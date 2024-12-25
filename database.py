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


class ColumnsComments:
    NAME_ = "Имя"
    TYPE_ = "Тип"
    SIZE_ = "Размер"
    MOD_ = "Дата изменения"
    RATING_ = "Рейтинг"


CACHE = sqlalchemy.Table(
    TABLE_NAME, METADATA,
    # Комментарии колонок используются только для сортировки.
    # Где есть комментарий — сортировка возможна.
    sqlalchemy.Column(ColumnNames.ID, sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column(ColumnNames.IMG, sqlalchemy.BLOB),
    sqlalchemy.Column(ColumnNames.NAME, sqlalchemy.Text, comment=ColumnsComments.NAME_),
    sqlalchemy.Column(ColumnNames.TYPE, sqlalchemy.Text, comment=ColumnsComments.TYPE_),
    sqlalchemy.Column(ColumnNames.SIZE, sqlalchemy.Integer, comment=ColumnsComments.SIZE_),
    sqlalchemy.Column(ColumnNames.MOD, sqlalchemy.Integer, comment=ColumnsComments.MOD_),
    sqlalchemy.Column(ColumnNames.RATING, sqlalchemy.Integer, comment=ColumnsComments.RATING_),
    sqlalchemy.Column(ColumnNames.RESOL, sqlalchemy.Integer),
    sqlalchemy.Column(ColumnNames.CATALOG, sqlalchemy.Text),
)


# создаем словарь из колонок таблицы CACHE
# ключ - внутреннее имя сортировки
# значение из комментария - текстовое имя сортировки
# на основке ORDER фомируется виджет со списком видов сортировки
ORDER: dict[str, str] = {
    clmn.name: clmn.comment
    for clmn in CACHE.columns
    if clmn.comment
}


class OrderItem:
    def __init__(self, src: str, size: int, mod: int, rating: int):
        super().__init__()
        self.src: str = src
        self.size: int = int(size)
        self.mod: int = int(mod)
        self.rating: int = rating

        # Извлечение имени файла из пути (например, "path/to/file.txt" -> "file.txt")
        self.name: str = os.path.split(self.src)[-1].strip()
            
        # Проверка: если путь ведёт к директории, то задаём тип FOLDER_TYPE.
        # Иначе определяем тип по расширению файла (например, ".txt").    
        if os.path.isdir(src):
            self.type_ = Static.FOLDER_TYPE
        else:
            self.type_ = os.path.splitext(self.src)[-1]

        # промежуточный аттрибут, нужен для GridSearch
        self.pixmap_: QPixmap = None


class Dbase:

    def __init__(self):
        self.conn_count = 0
        self.conn_max = 5

    def create_engine(self, path: str) -> sqlalchemy.Engine | None:

        if self.conn_count == self.conn_max:
            return None

        engine = sqlalchemy.create_engine(
            f"sqlite:///{path}",
            echo=False,
            connect_args={
                "check_same_thread": False,
                "timeout": 15
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

            print("database engine error", path)

            if os.path.exists(path):
                os.remove(path)
            self.create_engine(path=path)
