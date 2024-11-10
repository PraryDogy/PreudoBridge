import hashlib
import os

import numpy as np
import sqlalchemy

from database import CACHE, Dbase
from utils import Utils
import cv2


Dbase.init_db()

with Dbase.engine.connect() as conn:
    q = sqlalchemy.select(CACHE.c.id, CACHE.c.src).where(CACHE.c.id==89789)

    res = conn.execute(q).first()

    print(res)