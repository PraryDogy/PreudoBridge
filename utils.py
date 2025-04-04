import hashlib
import io
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
from PyQt5.QtCore import QRect, QRectF, QRunnable, QSize, Qt, QThreadPool
from PyQt5.QtGui import QColor, QFont, QImage, QPainter, QPixmap
from PyQt5.QtSvg import QSvgGenerator, QSvgRenderer
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
            with rawpy.imread(path) as raw:
                thumb = raw.extract_thumb()

            if thumb.format == rawpy.ThumbFormat.JPEG:
                img = Image.open(io.BytesIO(thumb.data))
                img = img.convert("RGB")

            elif thumb.format == rawpy.ThumbFormat.BITMAP:
                img = Image.fromarray(thumb.data)

            assert isinstance(img, Image.Image)

            try:
                exif = img.getexif()

                orientation_tag = 274  # Код тега Orientation
                if orientation_tag in exif:
                    orientation = exif[orientation_tag]
                    
                    # Коррекция поворота на основе EXIF-ориентации
                    if orientation == 3:
                        img = img.rotate(180, expand=True)
                    elif orientation == 6:
                        img = img.rotate(270, expand=True)
                    elif orientation == 8:
                        img = img.rotate(90, expand=True)

            except Exception as e:
                print(e)

            return np.array(img)

        except (Exception, rawpy._rawpy.LibRawDataError) as e:
            return None

    @classmethod
    def read_movie(cls, path: str, time_sec=1) -> np.ndarray | None:
        try:
            cap = cv2.VideoCapture(path)
            cap.set(cv2.CAP_PROP_POS_MSEC, time_sec * 1000)
            success, frame = cap.read()
            cap.release()

            if success:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                return frame
            else:
                return None

        except Exception:
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

            ".mov": cls.read_movie,
            ".mp4": cls.read_movie
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

    @classmethod
    def desaturate_image(cls, image: np.ndarray, factor=0.2):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return cv2.addWeighted(
            image,
            1 - factor,
            cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR),
            factor,
            0
        )

    @classmethod
    def create_generic(cls, file_extension: str):
        renderer = QSvgRenderer(Static.FILE_SVG)
        width = 133
        height = 133

        new_text = file_extension.replace(".", "")[:4].upper()
        new_filename = file_extension.replace(".", "") + ".svg"
        new_path = os.path.join(Static.ICONS_DIR, new_filename)

        # Создаем генератор SVG
        generator = QSvgGenerator()
        generator.setFileName(new_path)
        generator.setSize(QSize(width, height))
        generator.setViewBox(QRect(0, 0, width, height))

        # Рисуем на новом SVG с добавлением текста
        painter = QPainter(generator)
        renderer.render(painter)  # Рисуем исходный SVG
        
        # Добавляем текст
        painter.setPen(QColor(71, 84, 103))  # Цвет текста
        painter.setFont(QFont("Arial", 29, QFont.Bold))
        painter.drawText(QRectF(0, 75, width, 30), Qt.AlignCenter, new_text)
        
        painter.end()

        Dynamic.GENERIC_ICONS[new_filename] = new_path

        return new_path

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
        # cls.pool.waitForDone()


class PathFinder:
    VOLUMES = os.sep + "Volumes"
    EXTRA_PATHS = []

    @classmethod
    def get_result(cls, path: str) -> str | None:

        # удаляем новые строки, лишние слешы
        prepared = cls.prepare_path(path=path)

        if not prepared:
            return None

        elif os.path.exists(prepared):
            return prepared

        # превращаем путь в список 
        splited = cls.path_to_list(path=prepared)

        # игнорируем /Volumes/Macintosh HD
        volumes = cls.get_volumes()[1:]

        # см. аннотацию add_to_start
        paths = cls.add_to_start(splited_path=splited, volumes=volumes)

        res = cls.check_for_exists(paths=paths)

        if res in volumes:
            return None

        elif res:
            return res
        
        else:
            # см. аннотацию метода del_from_end
            paths = [
                ended_path
                for path_ in paths
                for ended_path in cls.del_from_end(path=path_)
            ]

            paths.sort(key=len, reverse=True)
            
            res = cls.check_for_exists(paths=paths)

            if res in volumes:
                return None
            
            elif res:
                return res

    @classmethod
    def get_volumes(cls) -> list[str]:
        return [
            entry.path
            for entry in os.scandir(cls.VOLUMES)
            if entry.is_dir()
        ]
    
    @classmethod
    def prepare_path(cls, path: str) -> str:
        path = path.replace("\\", os.sep)
        path = path.strip()
        path = path.strip("'").strip('"') # ковычки
        if path:
            return os.sep + path.strip(os.sep)
        else:
            return None

    @classmethod
    def path_to_list(cls, path: str) -> list[str]:
        return [
            i
            for i in path.split(os.sep)
            if i
        ]

    @classmethod
    def add_to_start(cls, splited_path: list, volumes: list[str]) -> list[str]:
        """
        Пример:
        >>> splited_path = ["Volumes", "Shares-1", "Studio", "MIUZ", "Photo", "Art", "Raw", "2025"]
        >>> volumes = ["/Volumes/Shares", "/Volumes/Shares-1"]
        [
            '/Volumes/Shares/Studio/MIUZ/Photo/Art/Raw/2025',
            '/Volumes/Shares/MIUZ/Photo/Art/Raw/2025',
            '/Volumes/Shares/Photo/Art/Raw/2025',
            '/Volumes/Shares/Art/Raw/2025',
            '/Volumes/Shares/Raw/2025',
            '/Volumes/Shares/2025',
            ...
            '/Volumes/Shares-1/Studio/MIUZ/Photo/Art/Raw/2025',
            '/Volumes/Shares-1/MIUZ/Photo/Art/Raw/2025',
            '/Volumes/Shares-1/Photo/Art/Raw/2025',
            ...
        ]
        """
        new_paths = []

        for vol in volumes:

            splited_path_copy = splited_path.copy()
            while len(splited_path_copy) > 0:

                new = vol + os.sep + os.path.join(*splited_path_copy)
                new_paths.append(new)
                splited_path_copy.pop(0)

        new_paths.sort(key=len, reverse=True)
        return new_paths
    
    @classmethod
    def check_for_exists(cls, paths: list[str]) -> str | None:
        for i in paths:
            if os.path.exists(i):
                return i
        return None
    
    @classmethod
    def del_from_end(cls, path: str) -> list[str]:
        """
        Пример:
        >>> path: "/sbc01/Shares/Studio/MIUZ/Photo/Art/Raw/2025"
        [
            "/sbc01/Shares/Studio/MIUZ/Photo/Art/Raw/2025",
            "/sbc01/Shares/Studio/MIUZ/Photo/Art/Raw",
            "/sbc01/Shares/Studio/MIUZ/Photo/Art",
            "/sbc01/Shares/Studio/MIUZ/Photo",
            "/sbc01/Shares/Studio/MIUZ",
            "/sbc01/Shares/Studio",
            "/sbc01/Shares",
            "/sbc01",
        ]
        """
        new_paths = []

        while path != os.sep:
            new_paths.append(path)
            path, _ = os.path.split(path)

        return new_paths