import os

import sqlalchemy
from sqlalchemy.orm import (Session, declarative_base, scoped_session,
                            sessionmaker)

from cfg import Config


class DbaseStorage:
    engine: sqlalchemy.Engine = None
    base = declarative_base()


class Dbase:
    @staticmethod
    def create_engine() -> sqlalchemy.Engine:
        DbaseStorage.engine = sqlalchemy.create_engine(
            f"sqlite:///{Config.db_file}",
            connect_args={"check_same_thread": False},
            echo=False
            )

    @staticmethod
    def get_session() -> Session:
        return Session(bind=DbaseStorage.engine)

    @staticmethod
    def vacuum():
        session = Dbase.get_session()
        try:
            session.execute(sqlalchemy.text("VACUUM"))
            session.commit()
        finally:
            session.close()

    @staticmethod
    def init_db():
        Dbase.create_engine()
        DbaseStorage.engine.connect()
        DbaseStorage.base.metadata.create_all(DbaseStorage.engine)

    @staticmethod
    def get_db_size() -> str:
        size_bytes = os.stat(Config.db_file).st_size

        size_mb = size_bytes / (1024 * 1024)
        
        if size_mb < 1024:
            return f"{size_mb:.2f}мб"
        else:
            size_gb = size_mb / 1024
            return f"{size_gb:.2f}гб"
    

class Cache(DbaseStorage.base):
    __tablename__ = "cache"
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    img = sqlalchemy.Column(sqlalchemy.LargeBinary)
    src = sqlalchemy.Column(sqlalchemy.Text, unique=True)
    root = sqlalchemy.Column(sqlalchemy.Text)
    size = sqlalchemy.Column(sqlalchemy.Integer)
    modified = sqlalchemy.Column(sqlalchemy.Integer)
    catalog = sqlalchemy.Column(sqlalchemy.Text)
    colors = sqlalchemy.Column(sqlalchemy.Text)
    stars = sqlalchemy.Column(sqlalchemy.Integer)