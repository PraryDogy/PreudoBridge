import os

import sqlalchemy
from sqlalchemy.exc import OperationalError

from cfg import Config, JsonData
from utils import Utils


class Engine:
    engine: sqlalchemy.Engine = None
    metadata = sqlalchemy.MetaData()

CACHE = sqlalchemy.Table(
    "cache", Engine.metadata,
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

ORDER: dict[dict[str, int]] = {
    clmn.name: {"text": clmn.comment, "index": ind}
    for ind, clmn in enumerate(CACHE.columns)
    if clmn.comment
    }

STATS = sqlalchemy.Table(
    'stats', Engine.metadata,
    sqlalchemy.Column('id', sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column('name', sqlalchemy.Text, unique=True),
    sqlalchemy.Column('size', sqlalchemy.Integer)
    )


class Dbase:
    @classmethod
    def init_db(cls):
        Engine.engine = sqlalchemy.create_engine(
            f"sqlite:///{Config.DB_FILE}",
            connect_args={"check_same_thread": False},
            echo=False
            )
        Engine.metadata.create_all(Engine.engine)
        cls.check_tables()
        cls.check_stats_main()
        cls.check_cache_size()

    @classmethod
    def check_stats_main(cls):
        stmt_select = sqlalchemy.select(STATS).where(STATS.c.name == "main")
        stmt_insert = sqlalchemy.insert(STATS).values(name="main", size=0)
        
        with Engine.engine.connect() as conn:
            result = conn.execute(stmt_select).first()
            if not result:
                conn.execute(stmt_insert)
                conn.commit()

    @classmethod
    def check_cache_size(cls):
        q_get_stats = sqlalchemy.select(STATS.c.size).where(STATS.c.name == "main")
        q_upd_stats = sqlalchemy.update(STATS).where(STATS.c.name == "main").values(size=0)
        q_del_cache = sqlalchemy.delete(CACHE)

        with Engine.engine.connect() as conn:

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

        with Engine.engine.connect() as conn:
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
        inspector = sqlalchemy.inspect(Engine.engine)

        TABLES = [CACHE, STATS]

        db_tables = inspector.get_table_names()
        res: bool = (list(i.name for i in TABLES) == db_tables)

        if not res:
            print("Не соответствие таблиц, создаю новую дб")
            os.remove(Config.DB_FILE)
            cls.init_db()
            return

        for table in TABLES:
            clmns = list(clmn.name for clmn in table.columns)
            db_clmns = list(clmn.get("name") for clmn in inspector.get_columns(table.name))
            res = bool(db_clmns == clmns)

            if not res:
                print(f"Не соответствие колонок в {table.name}, создаю новую дб")
                os.remove(Config.DB_FILE)
                cls.init_db()
                break
