from sqlalchemy import create_engine, Column, Integer, LargeBinary, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from database import Dbase, Cache

Dbase.init_db()
session = Dbase.get_session()
q = func.sum(func.length(Cache.img))
res = session.execute(q).scalar() or 0

gig_two = 2147483648
git_five = 5368709120
gig_ten = 10737418240

print(f"Общий размер в байтах: {res}")

session.close()