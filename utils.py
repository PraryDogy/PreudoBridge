import hashlib
import logging
import os
import subprocess
import traceback

import cv2
import numpy as np
import psd_tools
import rawpy
import tifffile
from imagecodecs.imagecodecs import DelayedImportError
from PIL import Image
from PyQt5.QtCore import QRunnable, Qt, QThreadPool
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QApplication, QVBoxLayout, QWidget

from cfg import GRID_SPACING, HASH_DIR, LEFT_MENU_W, MARGIN, THUMB_W, JsonData

psd_tools.psd.tagged_blocks.warn = lambda *args, **kwargs: None
psd_logger = logging.getLogger("psd_tools")
psd_logger.setLevel(logging.CRITICAL)

class Utils:
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
    def copy_path(cls, text: str):
        text_bytes = text.encode('utf-8')
        subprocess.run(['pbcopy'], input=text_bytes, check=True)
        return True
    
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
    def read_tiff(cls, path: str) -> np.ndarray | None:
        try:
            img = tifffile.imread(files=path)[:,:,:3]
            if str(object=img.dtype) != "uint8":
                img = (img/256).astype(dtype="uint8")
            return img
        except (Exception, tifffile.TiffFileError, RuntimeError, DelayedImportError) as e:
            cls.print_error(cls, e)
            print("try open tif with PIL")
            return cls.read_tiff_pil(path)
    
    @classmethod
    def read_tiff_pil(cls, path: str) -> np.ndarray | None:
        try:
            print("PIL: try open tif")
            img: Image = Image.open(path)
            # return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            return np.array(img)
        except Exception as e:
            Utils.print_error(parent=cls, error=e)
            return None

    @classmethod
    def read_psd(cls, path: str) -> np.ndarray | None:
        try:
            img = psd_tools.PSDImage.open(fp=path)
            img = img.composite()

            if img.mode == 'RGBA':
                img = img.convert('RGB')
            
            img = np.array(img)
            return img

        except Exception as e:
            cls.print_error(cls, e)
            return None
            
    @classmethod
    def read_jpg(cls, path: str) -> np.ndarray | None:
        try:
            image = cv2.imread(path, cv2.IMREAD_UNCHANGED)  # Чтение с альфа-каналом
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            return image
        except (Exception, cv2.error) as e:
            cls.print_error(cls, e)
            return None
        
    @classmethod
    def read_png(cls, path: str) -> np.ndarray | None:
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
            cls.print_error(cls, e)
            return None
        
    @classmethod
    def read_raw(cls, path: str) -> np.ndarray | None:
        try:
            img = rawpy.imread(path).postprocess()
            # img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            return img
        except (rawpy._rawpy.LibRawDataError) as e:
            cls.print_error(cls, e)
            return None

    @classmethod
    def read_image(cls, src: str) -> np.ndarray | None:
        src_lower: str = src.lower()

        if src_lower.endswith((".psd", ".psb")):
            img = cls.read_psd(src)

        elif src_lower.endswith((".tiff", ".tif")):
            img = cls.read_tiff(src)

        elif src_lower.endswith((".jpg", ".jpeg", "jfif")):
            img = cls.read_jpg(src)

        elif src_lower.endswith((".png")):
            img = cls.read_png(src)

        elif src_lower.endswith((".nef", ".cr2", ".cr3", ".arw", ".raf")):
            img = cls.read_raw(src)

        else:
            img = None

        return img
    
    # @classmethod
    # def pixmap_from_bytes(cls, image: bytes) -> QPixmap | None:
    #     if isinstance(image, bytes):
    #         ba = QByteArray(image)
    #         pixmap = QPixmap()
    #         pixmap.loadFromData(ba, "JPEG")
    #         return pixmap
    #     return None
    
    @classmethod
    def pixmap_from_array(cls, image: np.ndarray) -> QPixmap | None:
        if isinstance(image, np.ndarray):
            height, width, channel = image.shape
            bytes_per_line = channel * width
            qimage = QImage(image.tobytes(), width, height, bytes_per_line, QImage.Format.Format_RGB888)
            return QPixmap.fromImage(qimage)
        else:
            return None

    # @classmethod
    # def image_array_to_bytes(cls, image: np.ndarray, quality: int = 80) -> bytes | None:
    #     if isinstance(image, np.ndarray):
    #         img = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    #         res, buffer = cv2.imencode(".jpeg", img, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    #         image_io = io.BytesIO()
    #         image_io.write(buffer)
    #         img = image_io.getvalue()
    #         return img
    #     else:
    #         return None

    @classmethod
    def get_clmn_count(cls, width: int):
        w = sum((
            THUMB_W[JsonData.pixmap_size_ind],
            GRID_SPACING,
            MARGIN.get("w")
            ))
        return (width + LEFT_MENU_W) // w

    @classmethod
    def pixmap_scale(cls, pixmap: QPixmap, size: int) -> QPixmap:
        return pixmap.scaled(
            size,
            size,
            aspectRatioMode=Qt.AspectRatioMode.KeepAspectRatio,
            transformMode=Qt.TransformationMode.SmoothTransformation
            )

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

        class_name = parent.__class__.__name__
        error_message = str(error)

        print()
        print("#" * 100)
        print(f"{filepath}:{line_number}")
        print()
        print("ERROR:", error_message)
        print("#" * 100)
        print()

    @classmethod
    def get_folder_size_applescript(cls, path: str) -> float:
        applescript_file = "scripts/get_folder_size.scpt"
        script_command = ['osascript', applescript_file, path]
        try:
            result = subprocess.check_output(script_command).decode().strip()
            try:
                return float(result)
            except ValueError:
                return 0
        except subprocess.CalledProcessError as e:
            print(f"Error executing AppleScript: {e.output.decode().strip()}")
            return 0

    @classmethod
    def get_hash_path(cls, src: str) -> str:
        new_name = hashlib.md5(src.encode('utf-8')).hexdigest() + ".jpg"
        new_path = os.path.join(HASH_DIR, new_name[:2])
        os.makedirs(new_path, exist_ok=True)
        return os.path.join(new_path, new_name)
    
    @classmethod
    def write_image_hash(cls, output_path: str, array_img: np.ndarray) -> bool:
        try:
            array_img = cv2.cvtColor(array_img, cv2.COLOR_RGB2BGR)
            cv2.imwrite(output_path, array_img)
            return True
        except Exception as e:
            cls.print_error(parent=cls, error=e)
            return False
        
    @classmethod
    def read_image_hash(cls, src: str) -> np.ndarray | None:
        try:
            array_img = cv2.imread(src, cv2.IMREAD_UNCHANGED)
            return cv2.cvtColor(array_img, cv2.COLOR_BGR2RGB)
        except Exception as e:
            cls.print_error(parent=cls, error= e)
            return None
        
    @classmethod
    def get_bytes_size(cls, image: np.ndarray) -> int:
        return image.nbytes


class UThreadPool:
    pool: QThreadPool = None

    @classmethod
    def init(cls):
        cls.pool = QThreadPool().globalInstance()


class URunnable(QRunnable):
    def __init__(self):
        super().__init__()
        self._should_run: bool = True
        self._is_running: bool = False

    def set_should_run(self, b: bool):
        self._should_run: bool = b

    def set_is_running(self, b: bool):
        self._is_running = b

    def is_should_run(self):
        return self._should_run

    def is_running(self):
        return self._is_running