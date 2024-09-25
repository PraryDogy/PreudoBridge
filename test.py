from database import Dbase, ThumbsMd
import os
import sqlalchemy

Dbase.init_db()
session = Dbase.get_session()
img = "/Users/Loshkarev/Desktop/img_0162.jpg"
root = os.path.dirname(img)

q = sqlalchemy.select(ThumbsMd.src).filter(ThumbsMd.dir == root)
res = session.execute(q).fetchall()

for i in res:
    print(i)

session.close()


q = sqlalchemy.select(ThumbsMd.src).filter(ThumbsMd.dir == root)
res = session.execute(q).fetchall()

print(res)