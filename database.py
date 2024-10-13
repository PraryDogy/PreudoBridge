import sqlalchemy
import sqlalchemy.exc
from sqlalchemy.orm import Session, declarative_base

from cfg import Config


class DbaseStorage:
    engine: sqlalchemy.Engine = None
    base = declarative_base()


class Dbase:
    @staticmethod
    def get_session() -> Session:
        return Session(bind=DbaseStorage.engine)

    @staticmethod
    def init_db():

        DbaseStorage.engine = sqlalchemy.create_engine(
            f"sqlite:///{Config.db_file}",
            connect_args={"check_same_thread": False},
            echo=False
            )
        
        DbaseStorage.engine.connect()
        DbaseStorage.base.metadata.create_all(DbaseStorage.engine)
        Dbase.check_stats_main()

    @staticmethod
    def check_stats_main():
        sess = Dbase.get_session()

        try:
            q = sqlalchemy.select(Stats).where(Stats.name=="main")
            res = sess.execute(q).first()

            if not res:
                q = sqlalchemy.insert(Stats)
                q = q.values({"name": "main", "size": 0})
                sess.execute(q)
                sess.commit()

        except Exception as e:
            print("init db error:", e)

        sess.close()
        
    @staticmethod
    def c_commit(session: Session):
        session.commit()
        # print(session, "commit done")
    

class Cache(DbaseStorage.base):
    __tablename__ = "cache"
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    img = sqlalchemy.Column(sqlalchemy.LargeBinary)
    src = sqlalchemy.Column(sqlalchemy.Text, unique=True)
    root = sqlalchemy.Column(sqlalchemy.Text)
    size = sqlalchemy.Column(sqlalchemy.Integer)
    modified = sqlalchemy.Column(sqlalchemy.Integer)
    catalog = sqlalchemy.Column(sqlalchemy.Text, nullable=False)
    colors = sqlalchemy.Column(sqlalchemy.Text, nullable=False)
    stars = sqlalchemy.Column(sqlalchemy.Integer, nullable=False)


class Stats(DbaseStorage.base):
    __tablename__ = "stats"
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    name = sqlalchemy.Column(sqlalchemy.Text, unique=True)
    size = sqlalchemy.Column(sqlalchemy.Integer)