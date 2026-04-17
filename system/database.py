import os
import subprocess
import traceback

import sqlalchemy

from cfg import Static
from system.shared_utils import SharedUtils
from system.utils import Utils

_METADATA = sqlalchemy.MetaData()
_TABLE_NAME = "cache"

_CACHETABLE = sqlalchemy.Table(
    _TABLE_NAME, _METADATA,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("filename", sqlalchemy.Text),
    sqlalchemy.Column("rel_parent", sqlalchemy.Text),
    sqlalchemy.Column("fs_id", sqlalchemy.Text),
    sqlalchemy.Column("thumb_path", sqlalchemy.Text),
    sqlalchemy.Column("size", sqlalchemy.Integer),
    sqlalchemy.Column("mod", sqlalchemy.Integer),
    sqlalchemy.Column("rating", sqlalchemy.Integer),
)


class CacheTable:
    table = _CACHETABLE
    id = _CACHETABLE.c.id
    filename = _CACHETABLE.c.filename
    rel_parent = _CACHETABLE.c.rel_parent
    fs_id = _CACHETABLE.c.fs_id
    thumb_path = _CACHETABLE.c.thumb_path
    size = _CACHETABLE.c.size
    mod = _CACHETABLE.c.mod
    rating = _CACHETABLE.c.rating


class Dbase:
    main_engine: sqlalchemy.Engine
    
    @classmethod
    def create_engine(cls):
        return sqlalchemy.create_engine(
            f"sqlite:///{Static.external_db}",
            echo=False,
            connect_args={
                "check_same_thread": False,
                "timeout": 30
            }
        )

    @classmethod
    def init(cls):
        engine = sqlalchemy.create_engine(
            f"sqlite:///{Static.external_db}",
            echo=False,
            connect_args={"check_same_thread": False, "timeout": 30}
        )
        Dbase.main_engine = engine

        try:
            os.makedirs(Static.app_dir, exist_ok=True)
            _METADATA.create_all(engine)
            conn = Dbase.main_engine.connect()
            q = sqlalchemy.select(_CACHETABLE)
            conn.execute(q).first()
            conn.close()
        except Exception as e:
            print(f"Ошибка при открытии БД: {e}")
            if "no such column" in str(e):
                print("Не хватает колонок в существующей таблице, создаю новую")
                _METADATA.drop_all(engine)
                _METADATA.create_all(engine)
            else:
                log_file = os.path.join(Static.app_dir, "log.txt")
                with open(log_file, "w", encoding="utf-8") as f:
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
                    subprocess.Popen(["open", log_file])
                except Exception:
                    pass
                SharedUtils.exit_force()

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
