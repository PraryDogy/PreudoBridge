import os

import sqlalchemy
from sqlalchemy.exc import OperationalError

from cfg import DB_FILE, FOLDER_TYPE, JsonData
from utils import Utils

METADATA = sqlalchemy.MetaData()

CACHE = sqlalchemy.Table(
    "cache", METADATA,
    # комменты нужны только для сортировки. где есть коммент - сортировка возможна
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("src", sqlalchemy.Text, unique=True),
    sqlalchemy.Column("hash_path", sqlalchemy.Text),
    sqlalchemy.Column("root", sqlalchemy.Text),
    sqlalchemy.Column("catalog", sqlalchemy.Text, nullable=False),
    sqlalchemy.Column("name", sqlalchemy.Text, comment="Имя"),
    sqlalchemy.Column("type_", sqlalchemy.Text, comment="Тип"),
    sqlalchemy.Column("size", sqlalchemy.Integer, comment="Размер"),
    sqlalchemy.Column("mod", sqlalchemy.Integer, comment="Дата изменения"),
    sqlalchemy.Column("resol", sqlalchemy.Integer),
    sqlalchemy.Column("colors", sqlalchemy.Text, nullable=False, comment="Цвета"),
    sqlalchemy.Column("rating", sqlalchemy.Integer, nullable=False, comment="Рейтинг")
    )

ORDER: dict[str, dict[str, int]] = {
    clmn.name: {"text": clmn.comment, "index": ind}
    for ind, clmn in enumerate(CACHE.columns)
    if clmn.comment
    }

CACHE_CLMNS = [
    i.name
    for i in CACHE.columns
][1:]

class OrderItem:
    def __init__(self, src: str, size: int, mod: int, colors: str, rating: int):
        super().__init__()
        self.src: str = src
        self.size: int = size
        self.mod: int = mod
        self.colors: str = colors
        self.rating: int = rating

        self.name: str = os.path.split(self.src)[-1]
        
        if os.path.isdir(src):
            self.type_ = FOLDER_TYPE
        else:
            self.type_ = os.path.splitext(self.src)[-1]

    @classmethod
    def order_items(cls, order_items: list["OrderItem"]) -> list["OrderItem"]:
        
        order = list(ORDER.keys())

        if JsonData.sort not in order:
            print("database > OrderItem > order_items")
            print("Такой сортировки не существует:", JsonData.sort)
            print("Применяю сортировку из ORDER:", order[0])
            JsonData.sort = order[0]

        if JsonData.sort == "colors":
            key = lambda x: len(getattr(x, JsonData.sort))
        else:
            key = lambda x: getattr(x, JsonData.sort)

        rev = JsonData.reversed

        return sorted(order_items, key=key, reverse=rev)


class Dbase:
    engine: sqlalchemy.Engine = None

    @classmethod
    def init_db(cls):
        cls.engine = sqlalchemy.create_engine(
            f"sqlite:///{DB_FILE}",
            echo=False,
            connect_args={
                "check_same_thread": False,
                "timeout": 15
                }
                )
        METADATA.create_all(cls.engine)
        cls.toggle_wal(False)
        cls.check_tables()
        cls.check_values()

    @classmethod
    def toggle_wal(cls, value: bool):
        with cls.engine.connect() as conn:
            if value:
                conn.execute(sqlalchemy.text("PRAGMA journal_mode=WAL"))
            else:
                conn.execute(sqlalchemy.text("PRAGMA journal_mode=DELETE"))

    @classmethod
    def clear_db(cls):
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
    def check_tables(cls):
        inspector = sqlalchemy.inspect(cls.engine)

        TABLES = [CACHE]

        db_tables = inspector.get_table_names()
        res: bool = (list(i.name for i in TABLES) == db_tables)

        if not res:
            print("Не соответствие таблиц, создаю новую дб")
            os.remove(DB_FILE)
            cls.init_db()
            return

        for table in TABLES:
            clmns = list(clmn.name for clmn in table.columns)
            db_clmns = list(clmn.get("name") for clmn in inspector.get_columns(table.name))
            res = bool(db_clmns == clmns)

            if not res:
                print(f"Не соответствие колонок в {table.name}, создаю новую дб")
                os.remove(DB_FILE)
                cls.init_db()
                break


    @classmethod
    def check_values(cls):
        # проверяю сам себя, все ли колонки учитываются при создании
        # новой записи в БД
        values = cls.get_cache_values(*["" for i in range(0, 7)])
        assert list(values.keys()) == CACHE_CLMNS, "проверь get_cache_values"

    @classmethod
    def get_cache_values(
        cls, src, hash_path, name, type_, size, mod, resol
        ) -> dict[str, str]:

        return {
            "src": src,
            "hash_path": hash_path,
            "root": os.path.dirname(src),
            "catalog": "",
            "name": name,
            "type_": type_,
            "size": size,
            "mod": mod,
            "resol": resol,
            "colors": "",
            "rating": 0
            }
        
