import sqlalchemy

from cfg import Config


class Storage:
    engine: sqlalchemy.Engine = None
    metadata = sqlalchemy.MetaData()

CACHE = sqlalchemy.Table(
    "cache", Storage.metadata,
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
    'stats', Storage.metadata,
    sqlalchemy.Column('id', sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column('name', sqlalchemy.Text, unique=True),
    sqlalchemy.Column('size', sqlalchemy.Integer)
    )


class Dbase:
    @staticmethod
    def init_db():
        Storage.engine = sqlalchemy.create_engine(
            f"sqlite:///{Config.db_file}",
            connect_args={"check_same_thread": False},
            echo=False
            )
        Storage.metadata.create_all(Storage.engine)
        Dbase.check_stats_main()
        Dbase.check_cache_size()

    @staticmethod
    def check_stats_main():
        stmt_select = sqlalchemy.select(STATS).where(STATS.c.name == "main")
        stmt_insert = sqlalchemy.insert(STATS).values(name="main", size=0)
        
        with Storage.engine.connect() as connection:
            with connection.begin():
                result = connection.execute(stmt_select).first()
                if not result:
                    connection.execute(stmt_insert)

    @staticmethod
    def check_cache_size():
        q_get_stats = sqlalchemy.select(STATS.c.size).where(STATS.c.name == "main")
        q_upd_stats = sqlalchemy.update(STATS).where(STATS.c.name == "main").values(size=0)
        q_del_cache = sqlalchemy.delete(CACHE)

        with Storage.engine.connect() as conn:
            with conn.begin():

                current_size = conn.execute(q_get_stats).first()[0]
                config_size = Config.json_data["clear_db"] * (1024**3)

                if current_size >= config_size:

                    conn.execute(q_del_cache)
                    conn.execute(q_upd_stats)
                    
                conn.execute(sqlalchemy.text("VACUUM"))