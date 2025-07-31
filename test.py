from system.database import Dbase, CACHE
from sqlalchemy import select

src = "/Users/Loshkarev/Downloads/.preudobridge.db"
dbase = Dbase()
engine = dbase.create_engine(src)
conn = Dbase.open_connection(engine)

stmt = select(
    CACHE.c.id,
    CACHE.c.img,
    CACHE.c.size,
    CACHE.c.mod,
    CACHE.c.rating
)
stmt = stmt.where(CACHE.c.name=="daf")

id, bytes_img, size, mod, rating = conn.execute(stmt).first()

