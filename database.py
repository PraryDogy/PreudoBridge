import os

import sqlalchemy
from sqlalchemy.exc import OperationalError

from cfg import DB_FILE, FOLDER, IMG_EXT, JsonData
from utils import Utils

METADATA = sqlalchemy.MetaData()

CACHE = sqlalchemy.Table(
    "cache", METADATA,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("img", sqlalchemy.LargeBinary),
    sqlalchemy.Column("src", sqlalchemy.Text, unique=True),
    sqlalchemy.Column("root", sqlalchemy.Text),
    sqlalchemy.Column("catalog", sqlalchemy.Text, nullable=False),
    sqlalchemy.Column("name", sqlalchemy.Text, comment="Имя"),
    sqlalchemy.Column("type_", sqlalchemy.Text, comment="Тип"),
    sqlalchemy.Column("size", sqlalchemy.Integer, comment="Размер"),
    sqlalchemy.Column("mod", sqlalchemy.Integer, comment="Дата"),
    sqlalchemy.Column("colors", sqlalchemy.Text, nullable=False, comment="Цвета"),
    sqlalchemy.Column("rating", sqlalchemy.Integer, nullable=False, comment="Рейтинг")
    )

STATS = sqlalchemy.Table(
    'stats', METADATA,
    sqlalchemy.Column('id', sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column('name', sqlalchemy.Text, unique=True),
    sqlalchemy.Column('size', sqlalchemy.Integer)
    )

ORDER: dict[dict[str, int]] = {
    clmn.name: {"text": clmn.comment, "index": ind}
    for ind, clmn in enumerate(CACHE.columns)
    if clmn.comment
    }


class OrderItem:
    def __init__(self, src: str, size: int = None, mod: int = None, colors: str = None, rating: int = None):
        super().__init__()
        self.src: str = src
        self.size: int = 0 if size is None else size
        self.mod: int = 0 if mod is None else mod
        self.colors: str = "" if colors is None else colors
        self.rating: int = 0 if rating is None else rating

        self.name: str = os.path.split(self.src)[-1]
        
        if os.path.isdir(src):
            self.type_ = FOLDER
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
            connect_args={"check_same_thread": False},
            echo=False
            )
        METADATA.create_all(cls.engine)
        cls.check_tables()
        cls.check_stats_main()
        cls.check_cache_size()

    @classmethod
    def check_stats_main(cls):
        stmt_select = sqlalchemy.select(STATS).where(STATS.c.name == "main")
        stmt_insert = sqlalchemy.insert(STATS).values(name="main", size=0)
        
        with cls.engine.connect() as conn:
            result = conn.execute(stmt_select).first()
            if not result:
                conn.execute(stmt_insert)
                conn.commit()

    @classmethod
    def check_cache_size(cls):
        q_get_stats = sqlalchemy.select(STATS.c.size).where(STATS.c.name == "main")
        q_upd_stats = sqlalchemy.update(STATS).where(STATS.c.name == "main").values(size=0)
        q_del_cache = sqlalchemy.delete(CACHE)

        with cls.engine.connect() as conn:

            current_size = conn.execute(q_get_stats).scalar() or 0
            config_size = JsonData.clear_db * (1024**3)

            if current_size >= config_size:

                conn.execute(q_del_cache)
                conn.execute(q_upd_stats)
                conn.commit()

            conn.execute(sqlalchemy.text("VACUUM"))

    @classmethod
    def clear_db(cls):
        q_del_cache = sqlalchemy.delete(CACHE)
        q_upd_stats = sqlalchemy.update(STATS).where(STATS.c.name == "main").values(size=0)

        with cls.engine.connect() as conn:
            try:
                conn.execute(q_del_cache)
                conn.execute(q_upd_stats)
                conn.commit()
            except OperationalError as e:
                Utils.print_error(cls, e)
                return False

            conn.execute(sqlalchemy.text("VACUUM"))
            
        return True

    @classmethod
    def check_tables(cls):
        inspector = sqlalchemy.inspect(cls.engine)

        TABLES = [CACHE, STATS]

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
