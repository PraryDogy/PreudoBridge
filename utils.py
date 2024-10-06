import io
import logging
import subprocess
import traceback

import cv2
import numpy as np
import psd_tools
import tifffile
from PyQt5.QtCore import QByteArray
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QApplication, QFrame, QVBoxLayout, QWidget

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
    def read_tiff(src: str) -> np.ndarray:
        try:
            img = tifffile.imread(files=src)[:,:,:3]
            if str(object=img.dtype) != "uint8":
                img = (img/256).astype(dtype="uint8")
            # img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            return img
        except (tifffile.tifffile.TiffFileError) as e:
            print(traceback.format_exc())
            return Utils.read_psd(src)

    @staticmethod
    def read_psd(src: str) -> np.ndarray:
        try:
            img = psd_tools.PSDImage.open(fp=src)
            img = img.composite()

            if img.mode == 'RGBA':
                img = img.convert('RGB')
            
            img = np.array(img)
            return img

        except Exception as e:
            print(traceback.format_exc())
            return None
            
    @staticmethod
    def read_jpg(path: str) -> np.ndarray:
        try:
            image = cv2.imread(path, cv2.IMREAD_UNCHANGED)  # Чтение с альфа-каналом
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            return image
        except Exception as e:
            print("jpg read error, return None", e)
            return None
        
    @staticmethod
    def read_png(path: str) -> np.ndarray:
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
            print("read png error:", e)
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

        else:
            img = None

        return img
    
    @staticmethod
    def pixmap_from_bytes(image: bytes) -> QPixmap | None:
        try:
            ba = QByteArray(image)
            pixmap = QPixmap()
            pixmap.loadFromData(ba, "JPEG")
            return pixmap
        except Exception as e:
            print("pixmap from bytes error: ", e)
            return None
    
    @staticmethod
    def pixmap_from_array(image: np.ndarray) -> QPixmap:
        height, width, channel = image.shape
        bytes_per_line = channel * width
        qimage = QImage(image.tobytes(), width, height, bytes_per_line, QImage.Format.Format_RGB888)
        return QPixmap.fromImage(qimage)

    @staticmethod
    def image_array_to_bytes(image: np.ndarray, quality: int = 80) -> bytes | None:
        try:
            img = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            res, buffer = cv2.imencode(".jpeg", img, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
            image_io = io.BytesIO()
            image_io.write(buffer)
            img = image_io.getvalue()
            return img
        except Exception as e:
            print("image array to bytes err: ", e)

    @staticmethod
    def get_clmn_count(width: int):
        return width // (Config.thumb_size - 20)
    
    @staticmethod
    def deselect_selected_thumb():
        try:
            wid: QFrame = Config.selected_thumbnail
            wid.setFrameShape(QFrame.Shape.NoFrame)
        except (RuntimeError, AttributeError) as e:
            print("thumbnail > deselect prev thumb error:", e)