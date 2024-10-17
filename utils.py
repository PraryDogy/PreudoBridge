import io
import logging
import os
import subprocess
import traceback

import cv2
import numpy as np
import psd_tools
import rawpy
import tifffile
from PyQt5.QtCore import QByteArray
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QApplication, QVBoxLayout, QWidget

from cfg import Config

psd_tools.psd.tagged_blocks.warn = lambda *args, **kwargs: None
psd_logger = logging.getLogger("psd_tools")
psd_logger.setLevel(logging.CRITICAL)

class Utils:
    @staticmethod
    def clear_layout(layout: QVBoxLayout):
        if layout:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
                else:
                    Utils.clear_layout(item.layout())

    @staticmethod
    def copy_path(text: str):
        text_bytes = text.encode('utf-8')
        subprocess.run(['pbcopy'], input=text_bytes, check=True)
        return True
    
    @staticmethod
    def get_main_win(name: str ="SimpleFileExplorer") -> QWidget:
        for i in QApplication.topLevelWidgets():
            if name in str(i):
                return i

    @staticmethod
    def center_win(parent: QWidget, child: QWidget):
        geo = child.geometry()
        geo.moveCenter(parent.geometry().center())
        child.setGeometry(geo)

    @staticmethod
    def read_tiff(path: str) -> np.ndarray | None:
        try:
            img = tifffile.imread(files=path)[:,:,:3]
            if str(object=img.dtype) != "uint8":
                img = (img/256).astype(dtype="uint8")
            # img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            return img
        except (tifffile.tifffile.TiffFileError, RuntimeError) as e:
            Utils.print_error(Utils, e)
            return Utils.read_psd(path)

    @staticmethod
    def read_psd(path: str) -> np.ndarray | None:
        try:
            img = psd_tools.PSDImage.open(fp=path)
            img = img.composite()

            if img.mode == 'RGBA':
                img = img.convert('RGB')
            
            img = np.array(img)
            return img

        except Exception as e:
            print("read psd error", path, "\n")
            return None
            
    @staticmethod
    def read_jpg(path: str) -> np.ndarray | None:
        try:
            image = cv2.imread(path, cv2.IMREAD_UNCHANGED)  # Чтение с альфа-каналом
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            return image
        except Exception as e:
            print("jpg read error", path, "\n")
            return None
        
    @staticmethod
    def read_png(path: str) -> np.ndarray | None:
        try:
            image = cv2.imread(path, cv2.IMREAD_UNCHANGED)  # Чтение с альфа-каналом

            if image.shape[2] == 4:
                alpha_channel = image[:, :, 3] / 255.0
                rgb_channels = image[:, :, :3]
                background_color = np.array([255, 255, 255], dtype=np.uint8)
                background = np.full(rgb_channels.shape, background_color, dtype=np.uint8)
                converted = (rgb_channels * alpha_channel[:, :, np.newaxis] + background * (1 - alpha_channel[:, :, np.newaxis])).astype(np.uint8)
            else:
                converted = image

            converted = cv2.cvtColor(converted, cv2.COLOR_BGR2RGB)
            return converted
        except Exception as e:
            print("read png error:", path, "\n")
            return None
        
    @staticmethod
    def read_raw(path: str) -> np.ndarray | None:
        try:
            img = rawpy.imread(path).postprocess()
            # img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            return img
        except (rawpy._rawpy.LibRawDataError) as e:
            print("read raw error:", path, "\n")
            return None

    @staticmethod
    def read_image(src: str) -> np.ndarray | None:
        src_lower: str = src.lower()

        if src_lower.endswith((".psd", ".psb")):
            img = Utils.read_psd(src)

        elif src_lower.endswith((".tiff", ".tif")):
            img = Utils.read_tiff(src)

        elif src_lower.endswith((".jpg", ".jpeg", "jfif")):
            img = Utils.read_jpg(src)

        elif src_lower.endswith((".png")):
            img = Utils.read_png(src)

        elif src_lower.endswith((".nef", ".cr2", ".cr3", ".arw", ".raf")):
            img = Utils.read_raw(src)

        else:
            img = None

        return img
    
    @staticmethod
    def pixmap_from_bytes(image: bytes) -> QPixmap | None:
        if isinstance(image, bytes):
            ba = QByteArray(image)
            pixmap = QPixmap()
            pixmap.loadFromData(ba, "JPEG")
            return pixmap
        return None
    
    @staticmethod
    def pixmap_from_array(image: np.ndarray) -> QPixmap | None:
        if isinstance(image, np.ndarray):
            height, width, channel = image.shape
            bytes_per_line = channel * width
            qimage = QImage(image.tobytes(), width, height, bytes_per_line, QImage.Format.Format_RGB888)
            return QPixmap.fromImage(qimage)
        return None

    @staticmethod
    def image_array_to_bytes(image: np.ndarray, quality: int = 80) -> bytes | None:
        if isinstance(image, np.ndarray):
            img = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            res, buffer = cv2.imencode(".jpeg", img, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
            image_io = io.BytesIO()
            image_io.write(buffer)
            img = image_io.getvalue()
            return img
        return None

    @staticmethod
    def get_clmn_count(width: int):
        return (width + 150) // (Config.img_size + 10)


    @staticmethod
    def print_error(parent: object, error: Exception):
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

        class_name = parent.__class__.__name__
        error_message = str(error)

        print()
        print("#" * 100)
        print(f"{filepath}:{line_number}")
        print()
        print("ERROR:", error_message)
        print("#" * 100)
        print()