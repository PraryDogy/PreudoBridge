import os
import re

import sqlalchemy
from sqlalchemy.exc import OperationalError

from cfg import Dynamic, JsonData, Static
from utils import Utils

METADATA = sqlalchemy.MetaData()

TABLE_NAME = "cache"

ID = "id"
SRC = "src"
HASH_PATH = "hash_path"
ROOT = "root"
CATALOG = "catalog"
NAME = "name"
TYPE = "type_"
SIZE = "size"
MOD = "mod"
RESOL = "resol"
COLORS = "colors"
RATING = "rating"

NAME_ = "Имя"
TYPE_ = "Тип"
SIZE_ = "Размер"
MOD_ = "Дата изменения"
COLORS_ = "Цвета"
RATING_ = "Рейтинг"

CACHE = sqlalchemy.Table(
    TABLE_NAME, METADATA,
    # Комментарии колонок используются только для сортировки.
    # Где есть комментарий — сортировка возможна.
    sqlalchemy.Column(ID, sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column(SRC, sqlalchemy.Text, unique=True),
    sqlalchemy.Column(HASH_PATH, sqlalchemy.Text),
    sqlalchemy.Column(ROOT, sqlalchemy.Text),
    sqlalchemy.Column(CATALOG, sqlalchemy.Text, nullable=False),
    sqlalchemy.Column(NAME, sqlalchemy.Text, comment=NAME_),
    sqlalchemy.Column(TYPE, sqlalchemy.Text, comment=TYPE_),
    sqlalchemy.Column(SIZE, sqlalchemy.Integer, comment=SIZE_),
    sqlalchemy.Column(MOD, sqlalchemy.Integer, comment=MOD_),
    sqlalchemy.Column(RESOL, sqlalchemy.Integer),
    sqlalchemy.Column(COLORS, sqlalchemy.Text, nullable=False, comment=COLORS_),
    sqlalchemy.Column(RATING, sqlalchemy.Integer, nullable=False, comment=RATING_)
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
    def __init__(self, src: str, size: int, mod: int, colors: str, rating: int):
        super().__init__()
        self.src: str = src
        self.size: int = size
        self.mod: int = mod
        self.colors: str = colors
        self.rating: int = rating

        # Извлечение имени файла из пути (например, "path/to/file.txt" -> "file.txt")
        self.name: str = os.path.split(self.src)[-1]
            
        # Проверка: если путь ведёт к директории, то задаём тип FOLDER_TYPE.
        # Иначе определяем тип по расширению файла (например, ".txt").    
        if os.path.isdir(src):
            self.type_ = Static.FOLDER_TYPE
        else:
            self.type_ = os.path.splitext(self.src)[-1]


    # Как работает сортировка:
    # пользователь выбрал сортировку "по размеру"
    # в Dynamic в аттрибут "sort" записывается значение "size"
    # CACHE колонка имеет имя "size"
    # OrderItem имеет аттрибут "size"
    # на основе аттрибута "size" происходит сортировка списка из OrderItem

    @classmethod
    def order_items(cls, order_items: list["OrderItem"]) -> list["OrderItem"]:
        
        attr = Dynamic.sort
        rev = Dynamic.rev

        if attr == COLORS:

            # сортировка по цветовым меткам:
            # так как аттрибут OrderItem "colors" это список цветовых меток,
            # то мы производим сортировку по длине списка
            # а не сортируем по имени

            key = lambda order_item: len(getattr(order_item, attr))
            order_items.sort(key=key, reverse=rev)
            return order_items

        elif attr == NAME:

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
    engine: sqlalchemy.Engine

    @classmethod
    def init_db(cls):

        cls.engine = sqlalchemy.create_engine(
            url = f"sqlite:///{Static.DB_FILE}",
            echo = False,
            connect_args = {
                "check_same_thread": False,
                "timeout": 15
            }
        )

        METADATA.create_all(bind=cls.engine)
        cls.toggle_wal(value=False)
        cls.check_get_cache_values()

    @classmethod
    def toggle_wal(cls, value: bool):

        # WAL это опция с возможностью одновременного чтения и записи
        # в базу данных
        # работает так себе, поэтому мы ее выключаем
    
        with cls.engine.connect() as conn:

            if value:
                conn.execute(
                    statement = sqlalchemy.text("PRAGMA journal_mode=WAL")
                )

            else:
                conn.execute(
                    statement = sqlalchemy.text("PRAGMA journal_mode=DELETE")
                )

    @classmethod
    def clear_db(cls):

        # очистка CACHE, запускается из настроек приложения

        conn = cls.engine.connect()

        try:
            q_del_cache = sqlalchemy.delete(CACHE) 
            conn.execute(q_del_cache)

        except OperationalError as e:

            Utils.print_error(cls, e)
            conn.rollback()
            return False

        conn.commit()
        conn.execute(sqlalchemy.text("VACUUM"))
        conn.close()

        return True

    @classmethod
    def check_get_cache_values(cls):

        # проверка, что get_cache_values учитывает все колонки из CACHE
        # запускается один раз при инициации приложения

        # пустые аргументы, чтобы метод мог вернуть словарь
        kwargs_ = ["" for i in range(0, 7)]
        cache_values = cls.get_cache_values(*kwargs_)
        cache_values = list(cache_values.keys())

        # все колонки CACHE кроме id
        clmns = [i.name for i in CACHE.columns][1:]

        assert cache_values == clmns, "проверь get_cache_values"

    @classmethod
    def get_cache_values(cls, src, hash_path, name, type_, size, mod, resol):

        # метод который получает values для sqlalchemy.insert
        # словарь соответствует колонкам CACHE
        # если появится или будет удалена какая-либо колонка CACHE,
        # здесь это обязательно нужно отобразить

        return {
            SRC: src,  # Путь к файлу.
            HASH_PATH: hash_path,  # Хэш пути.
            ROOT: os.path.dirname(src),  # Корневая директория файла.
            CATALOG: "",  # Каталог (пока пустой).
            NAME: name,  # Имя файла.
            TYPE: type_,  # Тип файла.
            SIZE: size,  # Размер файла.
            MOD: mod,  # Дата изменения файла.
            RESOL: resol,  # Разрешение (если применимо).
            COLORS: "",  # Цвета (пока пустые).
            RATING: 0  # Рейтинг (по умолчанию 0).
        }
