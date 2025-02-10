import hashlib
import io
import logging
import os
import subprocess
import traceback
from datetime import datetime

import numpy as np
import psd_tools
import rawpy
import tifffile
from imagecodecs.imagecodecs import DelayedImportError
from PIL import Image
from PyQt5.QtCore import QRunnable, Qt, QThreadPool, QTimer
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QApplication, QVBoxLayout, QWidget

from cfg import Dynamic, Static, ThumbData

psd_tools.psd.tagged_blocks.warn = lambda *args, **kwargs: None
psd_logger = logging.getLogger("psd_tools")
psd_logger.setLevel(logging.CRITICAL)
VOLUMES = "Volumes"
USERS = "Users"

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

                # if channels > 3:
                #     img = psd_tools.PSDImage.open(psd_file)
                #     img = img.composite()
                #     print("psd tools")
                # else:
                #     print("PIL")
                #     img = Image.open(psd_file)

                img = psd_tools.PSDImage.open(psd_file)
                img = img.composite()
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
            img = img.convert("RGB")
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
            img = img.convert("RGB")
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
    def read_any(cls, path: str) -> np.ndarray | None:
        ...

    @classmethod
    def read_image(cls, path: str) -> np.ndarray | None:
        _, ext = os.path.splitext(path)
        ext = ext.lower()

        data = {
            ".psb": cls.read_psb,
            # ".psd": cls.read_psd,
            ".psd": cls.read_psb,

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

        fn = data.get(ext)

        if fn:
            cls.read_any = fn
            return cls.read_any(path=path)

        else:
            return None


class ImgConvert(Err):

    @classmethod
    def bytes_to_array(cls, blob: bytes) -> np.ndarray:

        try:
            with io.BytesIO(blob) as buffer:
                image = Image.open(buffer)
                return np.array(image)
            
        except Exception as e:
            Utils.print_error(parent=cls, error=e)
            return None

    @classmethod
    def numpy_to_bytes(cls, img_array: np.ndarray) -> bytes:

        try:
            with io.BytesIO() as buffer:
                image = Image.fromarray(img_array)
                image.save(buffer, format="JPEG")
                return buffer.getvalue()
            
        except Exception as e:
            Utils.print_error(parent=cls, error=e)
            return None


class Pixmap(Err):

    @classmethod
    def pixmap_from_array(cls, image: np.ndarray) -> QPixmap | None:

        if isinstance(image, np.ndarray) and QApplication.instance():
            if len(image.shape) == 3:
                height, width, channel = image.shape
            else:
                print("pixmap from array channels trouble", image.shape)
                return None

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
    

class Utils(Pixmap, ReadImage, ImgConvert):

    # вызывает segmentation fault
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
    def get_main_win(cls) -> QWidget:
        for i in QApplication.topLevelWidgets():
            if Static.MAIN_WIN_NAME in str(i):
                return i

    @classmethod
    def center_win(cls, parent: QWidget, child: QWidget):
        geo = child.geometry()
        geo.moveCenter(parent.geometry().center())
        child.setGeometry(geo)
     
    @classmethod
    def get_clmn_count(cls, width: int):
        w = sum(
            (
                ThumbData.THUMB_W[Dynamic.pixmap_size_ind],
                10
            )
        )
        # 10 пикселей к ширине виджета, чтобы он казался чуть шире
        # тогда при ресайзе окна позже потребуется новая колонка
        return (width + Static.LEFT_MENU_W) // w

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
    
    @classmethod
    def rm_rf(cls, path: str):

        result = subprocess.run(
            ['rm', '-rf', path],
            check=True,
            text=True,
            stderr=subprocess.PIPE
        )

        if result.returncode == 0:
            print("rm -rf успешно завершен", path)

    @classmethod
    def get_path_with_volumes(cls, path: str):

        # делаем возврат пути при первой итерации, потому что 
        # Macintosh HD всегда первый, а он то нам и нужен 

        if path.startswith(os.sep + USERS + os.sep):
            for i in  os.scandir(os.sep + VOLUMES):
                return i.path + path

        else:
            return path

    @classmethod
    def hash_filename(cls, filename: str):
        return hashlib.md5(filename.encode('utf-8')).hexdigest()
    
    @classmethod
    def get_partial_hash(cls, file_path: str):
        # Функция для вычисления частичного хеша файла.
        # Хешируются первые и последние 10 МБ файла (или весь файл, если он меньше 10 МБ).
        # Устанавливаем размер чанка для хеширования (10 МБ).
        chunk_size = 10 * 1024 * 1024  
        # Создаём объект SHA-256 для вычисления хеша.
        hash_func = hashlib.sha256()

        # Определяем размер файла.
        file_size = os.path.getsize(file_path)
        
        with open(file_path, 'rb') as f:
            # Если файл меньше или равен chunk_size, читаем и хешируем его целиком.
            if file_size <= chunk_size:
                hash_func.update(f.read())
            else:
                # Читаем и хешируем первые chunk_size байт файла.
                hash_func.update(f.read(chunk_size))
                # Переходим к последним chunk_size байтам файла и хешируем их.
                f.seek(-chunk_size, os.SEEK_END)
                hash_func.update(f.read(chunk_size))
        
        # Возвращаем итоговый хеш в шестнадцатеричном формате.
        return hash_func.hexdigest()


class URunnable(QRunnable):
    def __init__(self):
        super().__init__()
        self.should_run: bool = True
        self.is_running: bool = False
        self.name_: str = None
    
    @staticmethod
    def set_running_state(method: callable):

        def wrapper(self, *args, **kwargs):
            self.is_running = True
            method(self, *args, **kwargs)
            self.is_running = False

        return wrapper

    def get_name(self):
        return self.name_
    
    def set_name(self, text: str):
        self.name_ = text


class UThreadPool:
    pool: QThreadPool = None
    current: list[URunnable] = []

    @classmethod
    def init(cls):
        cls.pool = QThreadPool().globalInstance()

    @classmethod
    def start(cls, runnable: URunnable):

        new_current = [
            i
            for i in cls.current
            if i.is_running
        ]

        cls.current = new_current
    
        cls.current.append(runnable)
        cls.pool.start(runnable)

    @classmethod
    def stop_all(cls):
        for i in cls.current:
            i.should_run = False

        cls.current.clear()
        cls.pool.waitForDone()
