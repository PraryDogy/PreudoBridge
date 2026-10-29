import os
import subprocess
import traceback

import sqlalchemy
from sqlalchemy import event
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from cfg import Static
from system.utils import Utils

_METADATA = sqlalchemy.MetaData()
_TABLE_NAME = "cache"

# Версия схемы. При несовпадении с user_version в БД кэш пересоздается.
# Увеличивайте при изменении таблицы или индексов.
SCHEMA_VERSION = 2

_CACHETABLE = sqlalchemy.Table(
    _TABLE_NAME, _METADATA,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("filename", sqlalchemy.Text),
    sqlalchemy.Column("rel_parent", sqlalchemy.Text),
    sqlalchemy.Column("fs_id", sqlalchemy.Text),
    sqlalchemy.Column("thumb_path", sqlalchemy.Text),
    sqlalchemy.Column("size", sqlalchemy.Integer),
    sqlalchemy.Column("mod", sqlalchemy.Integer),
    sqlalchemy.Index("ix_cache_dir", "fs_id", "rel_parent"),
    sqlalchemy.UniqueConstraint(
        "fs_id", "rel_parent", "filename", "mod", "size",
        name="uq_cache_file",
    ),
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


def _make_engine() -> sqlalchemy.Engine:
    engine = sqlalchemy.create_engine(
        f"sqlite:///{Static.external_db}",
        echo=False,
        connect_args={"check_same_thread": False, "timeout": 30},
    )

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):
        # WAL: читатели не блокируют писателей, несколько процессов работают спокойнее
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.close()

    return engine


class Dbase:
    main_engine: sqlalchemy.Engine

    @classmethod
    def create_engine(cls):
        return _make_engine()

    @classmethod
    def insert_stmt(cls):
        # дубликаты (два окна одной папки) тихо пропускаются
        return sqlite_insert(_CACHETABLE).prefix_with("OR IGNORE")

    @classmethod
    def _migrate_if_needed(cls, engine: sqlalchemy.Engine):
        with engine.begin() as conn:
            version = conn.exec_driver_sql("PRAGMA user_version").scalar()
            if version != SCHEMA_VERSION:
                # кэш превью восстанавливаемый, можно пересоздать
                _METADATA.drop_all(conn)
                _METADATA.create_all(conn)
                conn.exec_driver_sql(f"PRAGMA user_version = {SCHEMA_VERSION}")

    @classmethod
    def init(cls):
        os.makedirs(Static.app_dir, exist_ok=True)
        cls.main_engine = _make_engine()
        try:
            cls._migrate_if_needed(cls.main_engine)
            with cls.main_engine.connect() as conn:
                conn.execute(sqlalchemy.select(_CACHETABLE)).first()
        except Exception:
            print("Ошибка при открытии БД")
            Utils.print_error()
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
            os._exit(1)

    @classmethod
    def commit(cls, conn: sqlalchemy.Connection) -> None:
        try:
            conn.commit()
        except Exception:
            Utils.print_error()
            conn.rollback()

    @classmethod
    def execute(cls, conn: sqlalchemy.Connection, query) -> sqlalchemy.CursorResult | None:
        try:
            return conn.execute(query)
        except Exception:
            Utils.print_error()
            conn.rollback()
            return None

    @classmethod
    def get_conn(cls, engine: sqlalchemy.Engine) -> sqlalchemy.Connection | None:
        try:
            return engine.connect()
        except Exception:
            Utils.print_error()
            return None

    @classmethod
    def close_conn(cls, conn: sqlalchemy.Connection):
        try:
            conn.close()
        except Exception:
            Utils.print_error()
            conn.rollback()
