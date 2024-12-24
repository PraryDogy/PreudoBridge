src_1 = "28.11.2024 в 12.11.31 royal 4_preview.jpg"
src_2 = "28.11.2024 в 12.11.31 royal 4_preview — копия.jpg"
db = "/Users/Loshkarev/Desktop/TEST IMAGES/test jpg/.preudobridge.db"
scan = "/Users/Loshkarev/Desktop/TEST IMAGES/test jpg"


from database import Dbase, CACHE
import sqlalchemy
import os


dbase = Dbase()
engine = dbase.create_engine(db)
conn = engine.connect()



for dir in os.scandir(scan):

    if dir.name.endswith(".jpg"):

        q = sqlalchemy.select(CACHE.c.id).where(CACHE.c.name == dir.name)
        res = conn.execute(q).mappings().first()

        print(res)

