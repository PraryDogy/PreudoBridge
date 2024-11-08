import hashlib
import os

import numpy as np
import sqlalchemy

from database import CACHE
from utils import Utils
import cv2


_THUMBS = "_thumbs"
DB_FILE = "db.db"

os.makedirs(_THUMBS, exist_ok=True)

engine = sqlalchemy.create_engine(
    f"sqlite:///{DB_FILE}",
    connect_args={"check_same_thread": False},
    echo=False
    )

conn = engine.connect()
q = sqlalchemy.select(CACHE.c.src, CACHE.c.img)
res = conn.execute(q).fetchall()

def get_hashed_name(src: str):
    return hashlib.md5(src.encode('utf-8')).hexdigest() + ".jpg"


for src, image_bytes in res:

    new_name = get_hashed_name(src)
    new_path = os.path.join(_THUMBS, new_name[:2])
    os.makedirs(new_path, exist_ok=True)

    new_src = os.path.join(new_path, new_name)

    image_array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    cv2.imwrite(new_src, image)
