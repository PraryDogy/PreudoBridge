import sqlalchemy

from cfg import Config


class Engine:
    engine: sqlalchemy.Engine = None
    metadata = sqlalchemy.MetaData()

CACHE = sqlalchemy.Table(
    "cache", Engine.metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("img", sqlalchemy.LargeBinary),
    sqlalchemy.Column("src", sqlalchemy.Text, unique=True),
    sqlalchemy.Column("root", sqlalchemy.Text),
    sqlalchemy.Column("size", sqlalchemy.Integer),
    sqlalchemy.Column("modified", sqlalchemy.Integer),
    sqlalchemy.Column("catalog", sqlalchemy.Text, nullable=False),
    sqlalchemy.Column("colors", sqlalchemy.Text, nullable=False),
    sqlalchemy.Column("stars", sqlalchemy.Integer, nullable=False)
    )


STATS = sqlalchemy.Table(
    'stats', Engine.metadata,
    sqlalchemy.Column('id', sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column('name', sqlalchemy.Text, unique=True),
    sqlalchemy.Column('size', sqlalchemy.Integer)
    )


class Dbase:
    @staticmethod
    def init_db():
        Engine.engine = sqlalchemy.create_engine(
            f"sqlite:///{Config.db_file}",
            connect_args={"check_same_thread": False},
            echo=False
            )
        Engine.metadata.create_all(Engine.engine)
        Dbase.check_stats_main()
        Dbase.check_cache_size()

    @staticmethod
    def check_stats_main():
        stmt_select = sqlalchemy.select(STATS).where(STATS.c.name == "main")
        stmt_insert = sqlalchemy.insert(STATS).values(name="main", size=0)
        
        with Engine.engine.connect() as conn:
            result = conn.execute(stmt_select).first()
            if not result:
                conn.execute(stmt_insert)
                conn.commit()

    @staticmethod
    def check_cache_size():
        q_get_stats = sqlalchemy.select(STATS.c.size).where(STATS.c.name == "main")
        q_upd_stats = sqlalchemy.update(STATS).where(STATS.c.name == "main").values(size=0)
        q_del_cache = sqlalchemy.delete(CACHE)

        with Engine.engine.connect() as conn:

            current_size = conn.execute(q_get_stats).scalar() or 0
            config_size = Config.json_data.get("clear_db") * (1024**3)

            if current_size >= config_size:

                conn.execute(q_del_cache)
                conn.execute(q_upd_stats)
                conn.commit()

            conn.execute(sqlalchemy.text("VACUUM"))