import os
from time import sleep

import sqlalchemy
from sqlalchemy.exc import IntegrityError, OperationalError

from system.utils import Utils

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


CACHE = sqlalchemy.Table(
    TABLE_NAME, METADATA,
    sqlalchemy.Column(ColumnNames.ID, sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column(ColumnNames.IMG, sqlalchemy.BLOB),
    sqlalchemy.Column(ColumnNames.NAME, sqlalchemy.Text),
    sqlalchemy.Column(ColumnNames.TYPE, sqlalchemy.Text),
    sqlalchemy.Column(ColumnNames.SIZE, sqlalchemy.Integer),
    sqlalchemy.Column(ColumnNames.MOD, sqlalchemy.Integer),
    sqlalchemy.Column(ColumnNames.RATING, sqlalchemy.Integer),
    sqlalchemy.Column(ColumnNames.RESOL, sqlalchemy.Integer),
    sqlalchemy.Column(ColumnNames.CATALOG, sqlalchemy.Text),
    sqlalchemy.Column(ColumnNames.PARTIAL_HASH, sqlalchemy.Text)
)


class Dbase:
    connections: list[sqlalchemy.Connection] = []

    def __init__(self):
        self.conn_count = 0
        self.conn_max = 1

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
                "timeout": 3
            }
        )

        try:
            # счетчик должен идти первым, потому что уже на инструкции
            # metadata.create_all уже может возникнуть ошибка

            self.conn_count += 1
            METADATA.create_all(engine)
            conn = Dbase.open_connection(engine)

            # проверяем доступность БД и соответствие таблицы
            q = sqlalchemy.select(CACHE)
            conn.execute(q).first()
            Dbase.close_connection(conn)

            return engine

        except SQL_ERRORS as e:
            error = Utils.print_error()

            if error is None or "unable to open database file" in error:
                return None

            if os.path.exists(path):
                os.remove(path)

            self.create_engine(path)

    @classmethod
    def commit_(cls, conn: sqlalchemy.Connection) -> None:
        try:
            conn.commit()
        except SQL_ERRORS as e:
            Utils.print_error()
            conn.rollback()

    @classmethod
    def execute_(cls, conn: sqlalchemy.Connection, query) -> sqlalchemy.CursorResult:
        try:
            return conn.execute(query)
        except SQL_ERRORS as e:
            Utils.print_error()
            conn.rollback()
            return None
    
    @classmethod
    def open_connection(cls, engine: sqlalchemy.Engine) -> sqlalchemy.Connection | None:
        try:
            return engine.connect()
        except SQL_ERRORS as e:
            Utils.print_error()
            return None
    
    @classmethod
    def close_connection(cls, conn: sqlalchemy.Connection):
        try:
            conn.close()
        except SQL_ERRORS as e:
            Utils.print_error()
            conn.rollback()