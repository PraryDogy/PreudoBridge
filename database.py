import os

import sqlalchemy
from sqlalchemy.orm import (Session, declarative_base, scoped_session,
                            sessionmaker)


class DbaseStorage:
    db_file = os.path.join(os.path.expanduser('~'), 'Desktop', 'preudo_db.db')
    engine: sqlalchemy.Engine = None
    base = declarative_base()


class Dbase:
    @staticmethod
    def create_engine() -> sqlalchemy.Engine:
        DbaseStorage.engine = sqlalchemy.create_engine(
            f"sqlite:///{DbaseStorage.db_file}",
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


class Cache(DbaseStorage.base):
    __tablename__ = "cache"
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    img = sqlalchemy.Column(sqlalchemy.LargeBinary)
    src = sqlalchemy.Column(sqlalchemy.Text, unique=True)
    dir = sqlalchemy.Column(sqlalchemy.Text)
    size = sqlalchemy.Column(sqlalchemy.Integer)
    modified = sqlalchemy.Column(sqlalchemy.Integer)
