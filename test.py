from database import Dbase, CACHE
import sqlalchemy
from cfg import JsonData


JsonData.init()
Dbase.init_db()


conn = Dbase.engine.connect()

q = ...