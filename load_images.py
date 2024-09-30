import os

import numpy as np
import sqlalchemy
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QLabel

from cfg import Config
from database import Cache, Dbase
from fit_img import FitImg
from utils import Utils


class LoadImagesThread(QThread):
    stop_thread = pyqtSignal()
    finished_thread = pyqtSignal()
    
    def __init__(self, finder_images: dict[tuple: QLabel], thumb_size: int):
        super().__init__()

        self.finder_images: dict[tuple: QLabel] = finder_images # (src, size, modified): QLabel
        self.remove_db_images: dict[tuple: str] = {}
        first_img = next(iter(self.finder_images))[0]
        self.root = os.path.dirname(first_img)

        self.db_images: dict = {}
        
        self.thumb_size = thumb_size
        self.flag = True
        self.stop_thread.connect(self.stop_thread_cmd)

        self.session = Dbase.get_session()

    def run(self):
        # print(self, "thread started")
        self.db_images: dict = self.get_db_images()
        self.load_already_images()
        self.create_new_images(images=self.finder_images)
        self.remove_images()
        self.session.commit()
        self.session.close()
        self.finished_thread.emit()
        # print(self, "thread finished")

    def create_new_images(self, images: dict):
        images_copy = images.copy()

        for (src, size, modified), widget in images_copy.items():
            # img = None
            src_lower: str = src.lower()

            if not self.flag:
                break

            if os.path.isdir(src):
                continue

            img = Utils.read_image(src)
            img = FitImg.start(img, Config.thumb_size)

            try:
                self.set_new_image(widget, img)
            except AttributeError as e:
                pass

            try:
                img = Utils.image_array_to_bytes(img)
                q = sqlalchemy.insert(Cache)
                q = q.values({
                    "img": img,
                    "src": src,
                    "root": self.root,
                    "size": size,
                    "modified": modified
                    })
                self.session.execute(q)
            except Exception as e:
                # print(e)
                pass

    def load_already_images(self):
        for (src, size, modified), bytearray_image in self.db_images.items():
            widget: QLabel = self.finder_images.get((src, size, modified))

            if not self.flag:
                break

            if widget:
                pixmap: QPixmap = Utils.pixmap_from_bytes(bytearray_image)
                widget.setPixmap(pixmap)
                self.finder_images.pop((src, size, modified))
            else:
                self.remove_db_images[(src, size, modified)] = ""

    def remove_images(self):
        for (src, size, modified), string in self.remove_db_images.items():
            q = sqlalchemy.delete(Cache)
            q = q.where(Cache.src==src, Cache.size==size, Cache.modified==modified)
            self.session.execute(q)

    def get_db_images(self):
        q = sqlalchemy.select(Cache.img, Cache.src, Cache.size, Cache.modified)
        q = q.where(Cache.root==self.root)
        res = self.session.execute(q).fetchall()
        return {
            (src, size, modified): img
            for img, src, size,  modified in res
            }

    def stop_thread_cmd(self):
        self.flag = False

    def set_new_image(self, widget: QLabel, image: np.ndarray):
        pixmap = Utils.pixmap_from_array(image)
        try:
            widget.setPixmap(pixmap)
        except RuntimeError:
            pass
