from database import Dbase, Engine, CACHE
import sqlalchemy

Dbase.init_db()
with Engine.engine.connect() as conn:
    with conn.begin():

        q = sqlalchemy.select(CACHE.c.colors)
        res = conn.execute(q).fetchall()


for i in res:
    a = type(i[0])
    print(a)