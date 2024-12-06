import hashlib
import logging
import os
import subprocess
import traceback
from datetime import datetime

import cv2
import numpy as np
import psd_tools
import rawpy
import tifffile
from imagecodecs.imagecodecs import DelayedImportError
from PIL import Image
from PyQt5.QtCore import QRunnable, Qt, QThreadPool, QTimer
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QApplication, QVBoxLayout, QWidget

from cfg import (GRID_SPACING, HASH_DIR, LEFT_MENU_W, MARGIN, THUMB_W, Dynamic,
                 JsonData, IMG_EXT)

psd_tools.psd.tagged_blocks.warn = lambda *args, **kwargs: None
psd_logger = logging.getLogger("psd_tools")
psd_logger.setLevel(logging.CRITICAL)


class Err:

    @classmethod
    def print_error(cls, parent: object, error: Exception):
        tb = traceback.extract_tb(error.__traceback__)

        # Попробуем найти первую строчку стека, которая относится к вашему коду.
        for trace in tb:
            filepath = trace.filename
            filename = os.path.basename(filepath)
            
            # Если файл - не стандартный модуль, считаем его основным
            if not filepath.startswith("<") and filename != "site-packages":
                line_number = trace.lineno
                break
        else:
            # Если не нашли, то берем последний вызов
            trace = tb[-1]
            filepath = trace.filename
            filename = os.path.basename(filepath)
            line_number = trace.lineno

        print(f"{filepath}:{line_number}")
        print("ERROR:", str(error))


class ReadImage(Err):

    @classmethod
    def read_tiff_tifffile(cls, path: str) -> np.ndarray | None:

        errs = (
            Exception,
            tifffile.TiffFileError,
            RuntimeError,
            DelayedImportError
        )

        try:
            img = tifffile.imread(files=path)[:,:,:3]
            if str(object=img.dtype) != "uint8":
                img = (img/256).astype(dtype="uint8")
            return img

        except errs as e:
            return None
    
    @classmethod
    def read_tiff_pil(cls, path: str) -> np.ndarray | None:

        try:
            img = Image.open(path)
            img = img.convert("RGB")
            img = np.array(img)
            return img

        except Exception as e:
            return None

    @classmethod
    def read_psd_pil(cls, path: str) -> np.ndarray | None:

        try:
            img = Image.open(path)
            img = img.convert("RGB")
            img = np.array(img)
            return img

        except Exception as e:
            return None

    @classmethod
    def read_psd_tools(cls, path: str) -> np.ndarray | None:

        try:
            img = psd_tools.PSDImage.open(fp=path)
            img = img.composite()
            img = np.array(img)
            return img

        except Exception as e:
            return None

    @classmethod
    def read_png_pil(cls, path: str) -> np.ndarray | None:
        try:
            img = Image.open(path)

            if img.mode == "RGBA":
                white_background = Image.new("RGBA", img.size, (255, 255, 255))
                img = Image.alpha_composite(white_background, img)

            img = img.convert("RGB")
            img = np.array(img)
            return img

        except Exception as e:
            cls.print_error(cls, e)
            return None

    @classmethod
    def read_png_cv2(cls, path: str) -> np.ndarray | None:
        try:
            image = cv2.imread(path, cv2.IMREAD_UNCHANGED)  # Чтение с альфа-каналом

            if image.shape[2] == 4:
                alpha_channel = image[:, :, 3] / 255.0
                rgb_channels = image[:, :, :3]
                background_color = np.array([255, 255, 255], dtype=np.uint8)
                background = np.full(
                    rgb_channels.shape, background_color, dtype=np.uint8
                )
                converted = (
                    rgb_channels * alpha_channel[:, :, np.newaxis] +
                    background * (1 - alpha_channel[:, :, np.newaxis])
                ).astype(np.uint8)

            else:
                converted = image

            return converted

        except Exception as e:
            cls.print_error(cls, e)
            return None

    @classmethod
    def read_jpg_pil(cls, path: str) -> np.ndarray | None:

        try:
            img = Image.open(path)
            img = np.array(img)
            return img

        except Exception as e:
            return None

    @classmethod
    def read_jpg_cv2(cls, path: str) -> np.ndarray | None:

        try:
            return cv2.imread(path, cv2.IMREAD_UNCHANGED)

        except (Exception, cv2.error) as e:
            return None

    @classmethod
    def read_raw(cls, path: str) -> np.ndarray | None:
        try:
            return rawpy.imread(path).postprocess()

        except rawpy._rawpy.LibRawDataError as e:
            return None

    @classmethod
    def read_image_for_view(cls, src: str):
        img = cls.read_image(src)
        return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    @classmethod
    def read_image(cls, src: str) -> np.ndarray | None:
        _, ext = os.path.splitext(src)
        ext = ext.lower()

        data = {
            ".psb": cls.read_psd_tools,
            ".psd": cls.read_psd_tools,

            ".tif": cls.read_tiff_tifffile,
            ".tiff": cls.read_tiff_tifffile,

            ".nef": cls.read_raw,
            ".cr2": cls.read_raw,
            ".cr3": cls.read_raw,
            ".arw": cls.read_raw,
            ".raf": cls.read_raw,

            ".jpg": cls.read_jpg_pil,
            ".jpeg": cls.read_jpg_pil,
            "jfif": cls.read_jpg_pil,

            ".png": cls.read_png_pil,
        }

        data_none = {
            ".tif": cls.read_tiff_pil,
            ".tiff": cls.read_tiff_pil,
            ".psd": cls.read_psd_tools,
            ".jpg": cls.read_jpg_cv2,
            ".jpeg": cls.read_jpg_cv2,
            "jfif": cls.read_jpg_cv2,
            ".png": cls.read_png_cv2,
        }

        img = None

        # если есть подходящее расширение то читаем файл
        if data.get(ext):
            img = data.get(ext)(src)

        else:
            return None

        # если прочитать не удалось, то пытаемся прочесть запасными функциями
        if img is None:
            img = data_none.get(ext)

        # либо None либо ndarray изображение
        return img


class Hash(Err):

    @classmethod
    def get_hash_path(cls, src: str) -> str:
        new_name = hashlib.md5(src.encode('utf-8')).hexdigest() + ".jpg"
        new_path = os.path.join(HASH_DIR, new_name[:2])
        os.makedirs(new_path, exist_ok=True)
        return os.path.join(new_path, new_name)
    
    @classmethod
    def write_image_hash(cls, output_path: str, array_img: np.ndarray) -> bool:
        try:
            img = cv2.cvtColor(array_img, cv2.COLOR_BGR2RGB)
            cv2.imwrite(output_path, img)
            return True
        except Exception as e:
            cls.print_error(parent=cls, error=e)
            return False

    @classmethod
    def read_image_hash(cls, src: str) -> np.ndarray | None:
        try:
            img = cv2.imread(src, cv2.IMREAD_UNCHANGED)
            return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        except Exception as e:
            print("read img hash error:", src)
            return None


class Pixmap:

    @classmethod
    def pixmap_from_array(cls, image: np.ndarray) -> QPixmap | None:

        if isinstance(image, np.ndarray) and QApplication.instance():
            height, width, channel = image.shape
            bytes_per_line = channel * width
            qimage = QImage(
                image.tobytes(),
                width,
                height,
                bytes_per_line,
                QImage.Format.Format_RGB888
            )
            return QPixmap.fromImage(qimage)

        else:
            return None

    @classmethod
    def pixmap_scale(cls, pixmap: QPixmap, size: int) -> QPixmap:

        return pixmap.scaled(
            size,
            size,
            aspectRatioMode=Qt.AspectRatioMode.KeepAspectRatio,
            transformMode=Qt.TransformationMode.SmoothTransformation
        )
    

class Utils(Hash, Pixmap, ReadImage):

    @classmethod
    def clear_layout(cls, layout: QVBoxLayout):
        if layout:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
                else:
                    cls.clear_layout(item.layout())

    @classmethod
    def write_to_clipboard(cls, text: str):
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        return True

    @classmethod
    def read_from_clipboard(cls):
        clipboard = QApplication.clipboard()
        return clipboard.text()

    @classmethod
    def get_main_win(cls, name: str ="SimpleFileExplorer") -> QWidget:
        for i in QApplication.topLevelWidgets():
            if name in str(i):
                return i

    @classmethod
    def center_win(cls, parent: QWidget, child: QWidget):
        geo = child.geometry()
        geo.moveCenter(parent.geometry().center())
        child.setGeometry(geo)
     
    @classmethod
    def get_clmn_count(cls, width: int):
        w = sum((
            THUMB_W[Dynamic.pixmap_size_ind],
            GRID_SPACING,
            MARGIN.get("w"),
            10
            ))
        # 10 пикселей к ширине виджета, чтобы он казался чуть шире
        # тогда при ресайзе окна позже потребуется новая колонка
        return (width + LEFT_MENU_W) // w

    @classmethod
    def get_f_size(cls, bytes_size: int) -> str:
        if bytes_size < 1024:
            return f"{bytes_size} байт"
        elif bytes_size < pow(1024,2):
            return f"{round(bytes_size/1024, 2)} КБ"
        elif bytes_size < pow(1024,3):
            return f"{round(bytes_size/(pow(1024,2)), 2)} МБ"
        elif bytes_size < pow(1024,4):
            return f"{round(bytes_size/(pow(1024,3)), 2)} ГБ"
        elif bytes_size < pow(1024,5):
            return f"{round(bytes_size/(pow(1024,4)), 2)} ТБ"

    @classmethod
    def get_f_date(cls, timestamp_: int) -> str:
        date = datetime.fromtimestamp(timestamp_).replace(microsecond=0)
        return date.strftime("%d.%m.%Y %H:%M")


class URunnable(QRunnable):
    def __init__(self):
        super().__init__()
        self.should_run: bool = True
        self.is_running: bool = False
    
    @staticmethod
    def set_running_state(method: callable):

        def wrapper(self, *args, **kwargs):
            self.is_running = True
            method(self, *args, **kwargs)
            self.is_running = False

        return wrapper


class UThreadPool:
    pool: QThreadPool = None
    current: list[URunnable] = []

    @classmethod
    def init(cls):
        cls.pool = QThreadPool().globalInstance()

    @classmethod
    def start(cls, runnable: URunnable):

        for i in cls.current:
            if not i.is_running:
                cls.current.remove(i)

        cls.current.append(runnable)
        cls.pool.start(runnable) 

    @classmethod
    def stop_all(cls):
        for i in cls.current:
            i.should_run = False

        for i in cls.current:
            if i.should_run:
                QTimer.singleShot(100, cls.stop_all)
                return