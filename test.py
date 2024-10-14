from database import Dbase, CACHE, Storage
import sqlalchemy
from sqlalchemy.exc import OperationalError

Dbase.init_db()
conn = Storage.engine.connect()



def get_db_data(src: str) -> dict | None:
    try:
        q = sqlalchemy.select(CACHE.c.img, CACHE.c.colors)
        q = q.where(CACHE.c.src == src)
        res = conn.execute(q).first()

        if res:
            return {"img": res.img, "colors": res.colors}
        else:
            return None

    except OperationalError:
        return None
