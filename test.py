from database import Dbase, CACHE
import os
import sqlalchemy

pa = "db.db"


dbase = Dbase()

engine = dbase.create_engine(pa)
    