import os

import sqlalchemy

from cfg import Static
from system.utils import Utils

METADATA = sqlalchemy.MetaData()
TABLE_NAME = "cache"


CACHE = sqlalchemy.Table(
    TABLE_NAME, METADATA,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("type_", sqlalchemy.Text),
    sqlalchemy.Column("size", sqlalchemy.Integer),
    sqlalchemy.Column("mod", sqlalchemy.Integer),
    sqlalchemy.Column("rating", sqlalchemy.Integer),
    sqlalchemy.Column("partial_hash", sqlalchemy.Text),
    sqlalchemy.Column("hashdir", sqlalchemy.Text),
)


class Clmns:
    id = CACHE.c.id
    type = CACHE.c.type_
    size = CACHE.c.size
    mod = CACHE.c.mod
    rating = CACHE.c.rating
    partial_hash = CACHE.c.partial_hash
    hashdir = CACHE.c.hashdir


class Dbase:
    engine: sqlalchemy.Engine

    @classmethod
    def init(cls):
        engine = sqlalchemy.create_engine(
            f"sqlite:///{Static.DB_FILE}",
            echo=False,
            connect_args={"check_same_thread": False, "timeout": 3}
        )

        try:
            METADATA.create_all(engine)
            conn = Dbase.open_connection(engine)
            q = sqlalchemy.select(CACHE)
            conn.execute(q).first()
            Dbase.close_connection(conn)
        except Exception as e:
            print(f"Ошибка при открытии БД: {e}")
            if "no such column" in str(e):
                METADATA.drop_all(engine)
                METADATA.create_all(engine)


    @classmethod
    def commit_(cls, conn: sqlalchemy.Connection) -> None:
        try:
            conn.commit()
        except Exception as e:
            Utils.print_error()
            conn.rollback()

    @classmethod
    def execute_(cls, conn: sqlalchemy.Connection, query) -> sqlalchemy.CursorResult:
        try:
            return conn.execute(query)
        except Exception as e:
            Utils.print_error()
            conn.rollback()
            return None
    
    @classmethod
    def open_connection(cls, engine: sqlalchemy.Engine) -> sqlalchemy.Connection | None:
        try:
            return engine.connect()
        except Exception as e:
            Utils.print_error()
            return None
    
    @classmethod
    def close_connection(cls, conn: sqlalchemy.Connection):
        try:
            conn.close()
        except Exception as e:
            Utils.print_error()
            conn.rollback()