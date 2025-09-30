import os

import sqlalchemy
from sqlalchemy.exc import OperationalError
from system.utils import Utils

METADATA = sqlalchemy.MetaData()
TABLE_NAME = "cache"

class ColumnNames:
    ID = "id"
    IMG = "img"
    NAME = "name"
    TYPE = "type_"
    SIZE = "size"
    MOD = "mod"
    RATING = "rating"
    RESOL = "resol" # не используется
    CATALOG = "catalog" # не используется
    PARTIAL_HASH = "partial_hash" # не используется


CACHE = sqlalchemy.Table(
    TABLE_NAME, METADATA,
    sqlalchemy.Column(ColumnNames.ID, sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column(ColumnNames.IMG, sqlalchemy.BLOB),
    sqlalchemy.Column(ColumnNames.NAME, sqlalchemy.Text),
    sqlalchemy.Column(ColumnNames.TYPE, sqlalchemy.Text),
    sqlalchemy.Column(ColumnNames.SIZE, sqlalchemy.Integer),
    sqlalchemy.Column(ColumnNames.MOD, sqlalchemy.Integer),
    sqlalchemy.Column(ColumnNames.RATING, sqlalchemy.Integer),
    sqlalchemy.Column(ColumnNames.RESOL, sqlalchemy.Integer), # не используется
    sqlalchemy.Column(ColumnNames.CATALOG, sqlalchemy.Text), # не используется
    sqlalchemy.Column(ColumnNames.PARTIAL_HASH, sqlalchemy.Text) # не используется
)


THUMBS = sqlalchemy.Table(
    "thumbs", METADATA,
    sqlalchemy.Column(ColumnNames.ID, sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column(ColumnNames.TYPE, sqlalchemy.Text),
    sqlalchemy.Column(ColumnNames.SIZE, sqlalchemy.Integer),
    sqlalchemy.Column(ColumnNames.MOD, sqlalchemy.Integer),
    sqlalchemy.Column(ColumnNames.RATING, sqlalchemy.Integer),
    sqlalchemy.Column(ColumnNames.RATING, sqlalchemy.Integer),
    sqlalchemy.Column(ColumnNames.RATING, sqlalchemy.Integer),
    sqlalchemy.Column(ColumnNames.PARTIAL_HASH, sqlalchemy.Text)
    
)



class Dbase:
    connections: list[sqlalchemy.Connection] = []

    def __init__(self):
        self.conn_count = 0
        self.conn_max = 1

    def create_engine(self, path: str) -> sqlalchemy.Engine | None:
        if self.conn_count >= self.conn_max:
            return None

        if os.path.isdir(path):
            print("Путь к БД должен быть файлом, а не папкой")
            return None

        engine = sqlalchemy.create_engine(
            f"sqlite:///{path}",
            echo=False,
            connect_args={"check_same_thread": False, "timeout": 3}
        )

        try:
            METADATA.create_all(engine)
            conn = Dbase.open_connection(engine)

            q = sqlalchemy.select(CACHE)
            conn.execute(q).first()
            Dbase.close_connection(conn)

            self.conn_count += 1
            return engine

        except OperationalError as e:
            print("Ошибка чтения БД:", e)
            try:
                os.remove(path)
                print("БД удалена, пересоздаём...")
            except Exception as e2:
                print("Ошибка удаления БД:", e2)
                return None

            # вторая (последняя) попытка
            try:
                return self.create_engine(path)
            except OperationalError as e3:
                print("Повторная ошибка чтения БД:", e3)
                return None

        except Exception as e:
            print(f"Ошибка при открытии БД: {e}")
            return None


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