import os
import subprocess
import traceback

import sqlalchemy

from cfg import Static
from system.utils import Utils

METADATA = sqlalchemy.MetaData()
TABLE_NAME = "cache"

CACHE = sqlalchemy.Table(
    TABLE_NAME, METADATA,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("name", sqlalchemy.Text),
    sqlalchemy.Column("type", sqlalchemy.Text),
    sqlalchemy.Column("size", sqlalchemy.Integer),
    sqlalchemy.Column("birth", sqlalchemy.Integer),
    sqlalchemy.Column("mod", sqlalchemy.Integer),
    sqlalchemy.Column("last_read", sqlalchemy.Integer),
    sqlalchemy.Column("rating", sqlalchemy.Integer),
    sqlalchemy.Column("partial_hash", sqlalchemy.Text),
    sqlalchemy.Column("thumb_path", sqlalchemy.Text),
)


class Clmns:
    id = CACHE.c.id
    name = CACHE.c.name
    type = CACHE.c.type
    size = CACHE.c.size
    birth = CACHE.c.birth
    mod = CACHE.c.mod
    last_read = CACHE.c.last_read
    rating = CACHE.c.rating
    partial_hash = CACHE.c.partial_hash
    thumb_path = CACHE.c.thumb_path


class Dbase:
    engine: sqlalchemy.Engine

    @classmethod
    def init(cls):
        engine = sqlalchemy.create_engine(
            f"sqlite:///{Static.external_db}",
            echo=False,
            connect_args={"check_same_thread": False, "timeout": 30}
        )
        Dbase.engine = engine

        try:
            METADATA.create_all(engine)
            conn = Dbase.engine.connect()
            q = sqlalchemy.select(CACHE)
            conn.execute(q).first()
            conn.close()
        except Exception as e:
            print(f"Ошибка при открытии БД: {e}")
            if "no such column" in str(e):
                print("Не хватает колонок в существующей таблице, создаю новую")
                METADATA.drop_all(engine)
                METADATA.create_all(engine)
            else:
                tb_file = os.path.join(Static.app_dir, "traceback.txt")
                with open(tb_file, "w", encoding="utf-8") as f:
                    f.write(
                        "ОТПРАВЬТЕ ЭТО РАЗРАБОТЧИКУ:\n"
                        "tg: evlosh\n"
                        "email: evlosh@gmail.com\n"
                        "\n"
                        "***************************************\n\n"
                        f"{traceback.format_exc()}\n"
                        "***************************************\n"
                    )
                try:
                    subprocess.Popen(["open", tb_file])
                except Exception:
                    pass
                os._exit(0)

    @classmethod
    def commit(cls, conn: sqlalchemy.Connection) -> None:
        try:
            conn.commit()
        except Exception as e:
            Utils.print_error()
            conn.rollback()

    @classmethod
    def execute(cls, conn: sqlalchemy.Connection, query) -> sqlalchemy.CursorResult:
        try:
            return conn.execute(query)
        except Exception as e:
            Utils.print_error()
            conn.rollback()
            return None
    
    @classmethod
    def get_conn(cls, engine: sqlalchemy.Engine) -> sqlalchemy.Connection | None:
        try:
            return engine.connect()
        except Exception as e:
            Utils.print_error()
            return None
    
    @classmethod
    def close_conn(cls, conn: sqlalchemy.Connection):
        try:
            conn.close()
        except Exception as e:
            Utils.print_error()
            conn.rollback()
