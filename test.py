import io
import os

import cv2
import numpy as np
import psd_tools
import sqlalchemy
import tifffile
from PIL import Image
from PyQt5.QtCore import QByteArray, QThread, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QLabel

from database import Cache, Dbase
from fit_img import FitImg

Dbase.init_db()
session = Dbase.get_session()
root = "/Users/Loshkarev/Desktop/test db"
bytearray_images: dict = {}

class PillowToBytes(io.BytesIO):
    def __init__(self, image: Image.Image) -> io.BytesIO:
        super().__init__()
        img = np.array(image)
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        res, buffer = cv2.imencode(".jpeg", img)
        self.write(buffer)



for img in os.listdir(root):

    img_src = os.path.join(root, img)
    img_stat = os.stat(img_src)
    size, modified = img_stat.st_size, img_stat.st_mtime

    img = Image.open(img_src)
    img = FitImg.start(img, 200, 200)

    bytearray_img = PillowToBytes(img)
    bytearray_images[bytearray_img.getvalue()] = (img_src, root, size, modified)

for img, (img_src, root, size, modified) in bytearray_images.items():
    q = sqlalchemy.insert(Cache)
    q = q.values({
        "img": img,
        "src": img_src,
        "root": root,
        "size": size,
        "modified": modified
        })
    session.execute(q)
session.commit()