from database import Dbase, STATS, Engine
import sqlalchemy

Dbase.init_db()

with Engine.engine.connect() as conn:
    q = sqlalchemy.update(STATS).values(size=555)
    res = conn.execute(q)