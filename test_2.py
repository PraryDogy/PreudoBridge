import sqlalchemy
from database import Dbase, Cache


src = "/Volumes/Macintosh HD/Users/Loshkarev/Desktop/MIUZ_0182.psd"

Dbase.init_db()
sess = Dbase.get_session()

q = sqlalchemy.select(Cache.img).where(Cache.src==src)
res = sess.execute(q).first()[0]


print(type(res))