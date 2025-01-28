import os
import re

import sqlalchemy
from PyQt5.QtGui import QPixmap
from sqlalchemy.exc import IntegrityError, OperationalError
import traceback
from cfg import Dynamic, Static

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
    sqlalchemy.Column(ColumnNames.PARTIAL_HASH, sqlalchemy.Text)
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

    # Как работает сортировка:
    # пользователь выбрал сортировку "по размеру"
    # в Dynamic в аттрибут "sort" записывается значение "size"
    # CACHE колонка имеет имя "size"
    # OrderItem имеет аттрибут "size"
    # на основе аттрибута "size" происходит сортировка списка из OrderItem

    @classmethod
    def sort_items(cls, order_items: list["OrderItem"]) -> list["OrderItem"]:
        
        attr = Dynamic.sort
        rev = Dynamic.rev

        if attr == ColumnNames.NAME:

            # сортировка по имени:
            # создаем список элементов, у которых в начале числовые символы
            # и список элементов, у которых в начале нечисловые символы
            # сортируем каждый список по отдельности
            # возвращаем объединенный список

            nums: list[OrderItem] = []
            abc: list[OrderItem] = []

            for i in order_items:

                if i.name[0].isdigit():
                    nums.append(i)

                else:
                    abc.append(i)

            # сортировка по числам в начале OrderItem.name
            key_num = lambda order_item: cls.get_nums(order_item)

            # сортировка по OrderItem.name
            key_abc = lambda order_item: getattr(order_item, attr)

            nums.sort(key=key_num, reverse=rev)
            abc.sort(key=key_abc, reverse=rev)

            return [*nums, *abc]

        else:

            key = lambda order_item: getattr(order_item, attr)
            order_items.sort(key=key, reverse=rev)
            return order_items

    # извлекаем начальные числа из order_item.name
    # по которым будет сортировка, например: "123 Te99st33" > 123
    # re.match ищет числа до первого нечислового символа
    @classmethod
    def get_nums(cls, order_item: "OrderItem"):

        return int(
            re.match(r'^\d+', order_item.name).group()
        )


class Dbase:

    def __init__(self):
        self.conn_count = 0
        self.conn_max = 5

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
            # print(traceback.format_exc())
            print("create engine error")

            if os.path.exists(path):
                os.remove(path)

            self.create_engine(path=path)
