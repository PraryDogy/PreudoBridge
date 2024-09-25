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


class PixmapFromBytes(QPixmap):
    def __init__(self, byte_array: QByteArray) -> QPixmap:
        super().__init__()

        ba = QByteArray(byte_array)
        self.loadFromData(ba, "JPEG")


class PillowToBytes(io.BytesIO):
    def __init__(self, image: Image.Image) -> io.BytesIO:
        super().__init__()
        img = np.array(image)
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        res, buffer = cv2.imencode(".jpeg", img)
        self.write(buffer)


class ImgUtils:

    @staticmethod
    def convert_tiff(src: str) -> Image.Image:
        try:
            img = tifffile.imread(files=src)[:,:,:3]
            if str(object=img.dtype) != "uint8":
                img = (img/256).astype(dtype="uint8")
            img = Image.fromarray(obj=img.astype("uint8"), mode="RGB")

            if img.mode == 'RGBA':
                img = img.convert('RGB')

            return img

        except Exception as e:
            print("tifffle error:", e, src)
            return None

    @staticmethod
    def convert_psd(src: str) -> Image.Image:
        try:
            img = psd_tools.PSDImage.open(fp=src).composite(ignore_preview=True)

            if img.mode == 'RGBA':
                img = img.convert('RGB')
            
            return img

        except Exception as e:
            print("psd tools error:", e, src)
            return None
            
    @staticmethod
    def read_jpg(path: str) -> Image.Image:
        image = cv2.imread(path, cv2.IMREAD_UNCHANGED)  # Чтение с альфа-каналом

        if image is None:
            print("Ошибка загрузки изображения")
            return None

        image = cv2.cvtColor(image, cv2.COLOR_BGRA2RGB)
        return Image.fromarray(image)
        
    @staticmethod
    def read_png(path: str) -> Image.Image:
        image = cv2.imread(path, cv2.IMREAD_UNCHANGED)  # Чтение с альфа-каналом

        if image is None:
            return None

        if image.shape[2] == 4:
            alpha_channel = image[:, :, 3] / 255.0
            rgb_channels = image[:, :, :3]
            background_color = np.array([255, 255, 255], dtype=np.uint8)
            background = np.full(rgb_channels.shape, background_color, dtype=np.uint8)
            converted = (rgb_channels * alpha_channel[:, :, np.newaxis] + background * (1 - alpha_channel[:, :, np.newaxis])).astype(np.uint8)
        else:
            converted = image

        pil_image = Image.fromarray(converted)
        return pil_image


class LoadImagesThread(QThread):
    stop_thread = pyqtSignal()
    finished_thread = pyqtSignal()
    
    def __init__(self, finder_images: list[dict], thumb_size: int):
        super().__init__()

        self.finder_images: list = finder_images # (src, size, modified): QLabel
        any_src_image = next(iter(self.finder_images))[0]
        root = os.path.dirname(any_src_image)

        self.db_images = self.get_db_images(root)
        self.filtered_images = {}
        
        self.thumb_size = thumb_size
        self.flag = True
        self.stop_thread.connect(self.stop_thread_cmd)

    def run(self):
        quit()

    def create_new_images(self, new_images):
        for image_data in new_images:

            image_data: dict
            src_lower: str = image_data["path"].lower()
            src: str = image_data["path"]
            img = None

            if not self.flag:
                break

            if os.path.isdir(src):
                self.set_default_image(image_data["widget"], "images/folder_210.png")
                continue

            elif src_lower.endswith((".tiff", ".tif")):
                img = ImgUtils.convert_tiff(image_data["path"])

            elif src_lower.endswith((".psd", ".psb")):
                img = ImgUtils.convert_psd(image_data["path"])

            elif src_lower.endswith((".jpg", ".jpeg")):
                img = ImgUtils.read_jpg(image_data["path"])

            elif src_lower.endswith((".png")):
                img = ImgUtils.read_png(image_data["path"])

            else:
                img = None
            
            try:
                self.set_new_image(image_data["widget"], img)
            except AttributeError as e:
                self.set_default_image(image_data["widget"], "images/file_210.png")

        self.finished_thread.emit()
        print("load images finished")

    def filter_images(self, db_images: dict, finder_images: dict):
        filtered_images = {
            "new": [],
            "del": [],
            "already": []
            }
        
        for (src, size, modified), bytearray_image in self.db_images.items():
            if (src, size, modified) not in self.finder_images:
                filtered_images["del"].append((src, size, modified))

    def get_db_images(self, root: str):
        session = Dbase.get_session()
        q = sqlalchemy.select(Cache.img, Cache.src, Cache.size, Cache.modified)
        q = q.where(Cache.dir==root)
        res = session.execute(q).fetchall()
        session.close()
        return {
            (src, size, modified): img
            for img, src, size,  modified in res
            }

    def stop_thread_cmd(self):
        self.flag = False

    def set_new_image(self, widget: QLabel, image: Image.Image):
        image = FitImg.fit(image, self.thumb_size, self.thumb_size)
        image = image.convert('RGBA')  # Преобразуем в RGBA

        data = np.array(image)
        height, width, channel = data.shape
        bytes_per_line = channel * width
        qimage = QPixmap.fromImage(QImage(data.data, width, height, bytes_per_line, QImage.Format_RGBA8888))

        try:
            widget.setPixmap(qimage)
        except RuntimeError:
            pass

    def set_default_image(self, widget: QLabel, png_path: str):
        pixmap = QPixmap(png_path)
        try:
            widget.setPixmap(pixmap)
        except RuntimeError:
            pass