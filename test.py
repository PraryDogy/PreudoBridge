from database import Dbase, Engine, CACHE, sqlalchemy
from sqlalchemy.exc import IntegrityError, OperationalError
from utils import Utils

Dbase.init_db()
conn = Engine.engine.connect()

class Test:
    def __init__(self):
        src = "/Volumes/Macintosh HD/Users/Morkowik/Downloads/1-2 Крист img040 — копия.jpg"
        # src = "test"
        q = sqlalchemy.insert(CACHE).values(
            src = src,
            catalog = "",
            colors = "",
            stars = ""
            )
        try:
            conn.execute(q)
        except IntegrityError as er:
            Utils.print_err(parent=self, error=er)
        except OperationalError:
            Utils.print_err(parent=self, error=er)

Test()