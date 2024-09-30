from database import Dbase, Cache
import sqlalchemy

Dbase.init_db()
sess = Dbase.get_session()
q = sqlalchemy.select(Cache.img).where(Cache.src=="/Volumes/Macintosh HD/Users/Loshkarev/Desktop/MIUZ_0158 2.jpg")
res = sess.execute(q).first()

print(res)