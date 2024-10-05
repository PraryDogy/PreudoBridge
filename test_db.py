import sqlalchemy
from database import Dbase, Cache
from sqlalchemy import Table
import os
from cfg import Config

Dbase.init_db()
sess = Dbase.get_session()

try:
    q = sqlalchemy.select(Cache)
    res = sess.execute(q).first()
except sqlalchemy.exc.OperationalError as e:
    print(e)
    os.remove(Config.db_file)
    Dbase.init_db()