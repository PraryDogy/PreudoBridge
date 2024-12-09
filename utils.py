import hashlib
import logging
import os
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

from cfg import GRID_SPACING, HASH_DIR, LEFT_MENU_W, MARGIN, THUMB_W, Dynamic

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
    def read_tiff(cls, path: str) -> np.ndarray | None:

        errors = (
            tifffile.TiffFileError,
            RuntimeError,
            DelayedImportError,
            Exception
        )

        try:
            # Оставляем только три канала (RGB)
            img = tifffile.imread(files=path)
            img = img[..., :3]

            # Проверяем, соответствует ли тип данных изображения uint8.
            # `uint8` — это 8-битный целочисленный формат данных, где значения
            # пикселей лежат в диапазоне [0, 255].
            # Большинство изображений в RGB используют именно этот формат
            # для хранения данных.
            # Если тип данных не `uint8`, требуется преобразование.
            if str(object=img.dtype) != "uint8":

                # Если тип данных отличается, то предполагаем, что значения
                # пикселей выходят за пределы диапазона [0, 255].
                # Например, они могут быть в формате uint16 (диапазон [0, 65535]).
                # Для преобразования выполняем нормализацию значений.
                # Делим на 256, чтобы перевести диапазон [0, 65535] в [0, 255]:
                # 65535 / 256 ≈ 255 (максимальное значение в uint8).
                # Приводим типданных массива к uint8.
                img = (img / 256).astype(dtype="uint8")

            return img

        except errors as e:

            print("error read tiff", path, e)

            try:
                img = Image.open(path)
                img = img.convert("RGB")
                return np.array(img)

            except Exception:
                return None


    @classmethod
    def read_psd(cls, path: str) -> np.ndarray | None:

        with open(path, "rb") as psd_file:

            # Проверяем, что файл имеет правильную подпись PSD/PSB:
            # В начале файла (первые 4 байта) должна быть строка '8BPS', 
            # которая является стандартной подписью для форматов PSD и PSB.
            # Если подпись не совпадает, файл не является корректным PSD/PSB.
            if psd_file.read(4) != b"8BPS":
                return None

            # Переходим к байту 12, где согласно спецификации PSD/PSB
            # содержится число каналов изображения. Число каналов (2 байта)
            # определяет, сколько цветовых и дополнительных каналов содержится в файле.
            psd_file.seek(12)

            # Считываем число каналов (2 байта, big-endian формат,
            # так как PSD/PSB используют этот порядок байтов).
            channels = int.from_bytes(psd_file.read(2), byteorder="big")

            # Возвращаем указатель в начало файла (offset = 0),
            # чтобы psd-tools или Pillow могли корректно прочитать файл с самого начала.
            # Это важно, так как мы изменяли положение указателя для проверки структуры файла.
            psd_file.seek(0)

            try:

                if channels > 3:
                    img = psd_tools.PSDImage.open(psd_file)
                    img = img.composite()
                else:
                    img = Image.open(psd_file)

                img = img.convert("RGB")
                return np.array(img)

            except Exception as e:

                print("utils > error read psd", "src:", path)
                print(e)
                return None

        
    @classmethod
    def read_psb(cls, path: str):

        try:
            img = psd_tools.PSDImage.open(path)
            img = img.composite()
            return np.array(img)

        except Exception as e:
            print("utils > error read psd", "src:", path)
            print(e)
            return None

    @classmethod
    def read_png(cls, path: str) -> np.ndarray | None:
        try:
            img = Image.open(path)

            if img.mode == "RGBA":
                white_background = Image.new("RGBA", img.size, (255, 255, 255))
                img = Image.alpha_composite(white_background, img)

            img = img.convert("RGB")
            img = np.array(img)
            return img

        except Exception as e:
            print("error read png pil", str)
            return None

    @classmethod
    def read_jpg(cls, path: str) -> np.ndarray | None:

        try:
            img = Image.open(path)
            img = np.array(img)
            return img

        except Exception as e:
            return None

    @classmethod
    def read_raw(cls, path: str) -> np.ndarray | None:
        try:
            return rawpy.imread(path).postprocess()

        except rawpy._rawpy.LibRawDataError as e:
            return None

    @classmethod
    def read_image(cls, full_src: str) -> np.ndarray | None:
        _, ext = os.path.splitext(full_src)
        ext = ext.lower()

        data = {
            ".psb": cls.read_psb,
            ".psd": cls.read_psd,

            ".tif": cls.read_tiff,
            ".tiff": cls.read_tiff,

            ".nef": cls.read_raw,
            ".cr2": cls.read_raw,
            ".cr3": cls.read_raw,
            ".arw": cls.read_raw,
            ".raf": cls.read_raw,

            ".jpg": cls.read_jpg,
            ".jpeg": cls.read_jpg,
            "jfif": cls.read_jpg,

            ".png": cls.read_png,
        }

        read_img_func = data.get(ext)

        if read_img_func:
            img = read_img_func(full_src)

        else:
            img = None

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