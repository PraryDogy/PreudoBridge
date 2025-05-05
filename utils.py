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
from PyQt5.QtCore import (QRect, QRectF, QRunnable, QSize, Qt, QThreadPool,
                          pyqtBoundSignal)
from PyQt5.QtGui import QColor, QFont, QImage, QPainter, QPixmap
from PyQt5.QtSvg import QSvgGenerator, QSvgRenderer
from PyQt5.QtWidgets import QApplication

from cfg import Dynamic, Static

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
        try:
            img = tifffile.imread(path)
            # Проверяем, что изображение трёхмерное
            if img.ndim == 3:
                channels = min(img.shape)
                channels_index = img.shape.index(channels)
                # Транспонируем, если каналы на первом месте
                if channels_index == 0:
                    img = img.transpose(1, 2, 0)
                # Ограничиваем количество каналов до 3
                if channels > 3:
                    img = img[:, :, :3]
                # Преобразуем в uint8, если тип другой
                if str(img.dtype) != "uint8":
                    img = (img / 256).astype(dtype="uint8")
            # Если изображение уже 2D, просто показываем его
            elif img.ndim == 2:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            return img
        except (tifffile.TiffFileError, RuntimeError, DelayedImportError, Exception) as e: 
            print("error read tiff, open pil", path, e)
            try:
                img = Image.open(path)
                img = img.convert("RGB")
                array_img = np.array(img)
                img.close()
                return array_img
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
                img = psd_tools.PSDImage.open(psd_file)
                img = img.composite()
                img = img.convert("RGB")
                array_img = np.array(img)
                # предотвращает segmentation fault
                img.close()
                return array_img
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
            array_img = np.array(img)
            return array_img
        except Exception as e:
            print("utils > error read psd", "src:", path)
            print(e)
            return None

    """
    read jpg, png, raw
    PIL заменен на cv2, чтобы избежать segmentation fault / bus error
    """

    # @classmethod
    # def read_png(cls, path: str) -> np.ndarray | None:
    #     try:
    #         img = Image.open(path)
    #         if img.mode == "RGBA":
    #             white_background = Image.new("RGBA", img.size, (255, 255, 255))
    #             img = Image.alpha_composite(white_background, img)
    #         img = img.convert("RGB")
    #         array_img = np.array(img)
    #         img.close()
    #         return array_img
    #     except Exception as e:
    #         print("error read png pil", str)
    #         return None

    # @classmethod
    # def read_jpg(cls, path: str) -> np.ndarray | None:
    #     try:
    #         img = Image.open(path)
    #         img = img.convert("RGB")
    #         array_img = np.array(img)
    #         img.close()
    #         return array_img
    #     except Exception as e:
    #         print("read jpg error", e)
    #         return None

    # @classmethod
    # def read_raw(cls, path: str) -> np.ndarray | None:
    #     try:
    #         with rawpy.imread(path) as raw:
    #             thumb = raw.extract_thumb()
    #         if thumb.format == rawpy.ThumbFormat.JPEG:
    #             img = Image.open(io.BytesIO(thumb.data))
    #             img = img.convert("RGB")
    #         elif thumb.format == rawpy.ThumbFormat.BITMAP:
    #             img: Image.Image = Image.fromarray(thumb.data)
    #         try:
    #             exif = img.getexif()
    #             orientation_tag = 274  # Код тега Orientation
    #             if orientation_tag in exif:
    #                 orientation = exif[orientation_tag]
    #                 # Коррекция поворота на основе EXIF-ориентации
    #                 if orientation == 3:
    #                     img = img.rotate(180, expand=True)
    #                 elif orientation == 6:
    #                     img = img.rotate(270, expand=True)
    #                 elif orientation == 8:
    #                     img = img.rotate(90, expand=True)
    #         except Exception as e:
    #             print(e)
    #         array_img = np.array(img)
    #         img.close()
    #         return array_img
    #     except (Exception, rawpy._rawpy.LibRawDataError) as e:
    #         return None


    """
    read jpg, png, raw
    PIL заменен на cv2, чтобы избежать segmentation fault / bus error
    """

    @classmethod
    def read_png(cls, path: str) -> np.ndarray | None:
        try:
            # Загружаем изображение с флагом IMREAD_UNCHANGED, чтобы сохранить альфа-канал (если он есть)
            img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
            
            # Проверяем, что изображение было успешно загружено
            if img is None:
                raise ValueError("Image not loaded")
            
            # Проверяем, есть ли альфа-канал у изображения (RGBA)
            # Если изображение состоит из 4 каналов (RGB + Alpha), то выполняем обработку
            if img.shape[2] == 4:
                # Извлекаем альфа-канал (4-й канал), который представляет прозрачность пикселей
                # Альфа-канал содержит значения от 0 (полностью прозрачный) до 255 (полностью непрозрачный)
                # Нормализуем альфа-канал, делая его диапазон от 0 до 1
                alpha = img[:, :, 3] / 255.0  
                
                # Извлекаем RGB каналы (первые 3 канала, игнорируя альфа-канал)
                bgr = img[:, :, :3]
                
                # Создаём белый фон того же размера, что и исходное изображение
                # np.ones_like создаёт массив той же формы, но с единичными значениями
                # Белый фон (в формате BGR)
                white_bg = np.ones_like(bgr, dtype=np.uint8) * 255
                
                # Смешиваем изображение с белым фоном в зависимости от альфа-канала
                # Если альфа-канал равен 1 (полностью непрозрачный), то берём только RGB изображение
                # Если альфа-канал равен 0 (полностью прозрачный), то используем белый фон
                img = (bgr * alpha[..., None] + white_bg * (1 - alpha[..., None])).astype(np.uint8)
            
            # Преобразуем изображение из формата BGR в RGB
            # OpenCV использует BGR, а для большинства библиотек, включая Pillow, используется RGB
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            
            return img
        except Exception as e:
            # Если произошла ошибка, выводим её
            print("error read png cv2:", e)
            return None

    @classmethod
    def read_jpg(cls, path: str) -> np.ndarray | None:
        try:
            img = cv2.imread(path)
            if img is None:
                raise ValueError("Image not loaded")
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            return img
        except Exception as e:
            print("read jpg cv2 error", e)
            return None

    @classmethod
    def read_raw(cls, path: str) -> np.ndarray | None:
        try:
            with rawpy.imread(path) as raw:
                thumb = raw.extract_thumb()
            
            if thumb.format == rawpy.ThumbFormat.JPEG:
                img_array = np.asarray(bytearray(thumb.data), dtype=np.uint8)
                # Декодируем изображение, получаем изображение в формате BGR
                img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                # Преобразуем из BGR в RGB, чтобы цвета отображались корректно
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            # Если превью в формате BMP, преобразуем в изображение с использованием OpenCV
            elif thumb.format == rawpy.ThumbFormat.BITMAP:
                # Если данные уже в RGB (формат BMP), просто используем их
                img = thumb.data
                # Если данные в BGR, тогда нужно преобразовать в RGB
                if len(img.shape) == 3 and img.shape[2] == 3:  # Проверяем, что изображение в BGR
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            return img
        except (Exception, rawpy._rawpy.LibRawDataError) as e:
            print(f"Error reading raw file: {e}")
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
            ".jfif": cls.read_jpg,

            ".png": cls.read_png,

            ".mov": cls.read_movie,
            ".mp4": cls.read_movie
        }

        fn = data.get(ext)

        if fn:
            cls.read_any = fn
            return cls.read_any(path)

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
    _NULL = object()

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
    def normalize_slash(cls, path: str):
        """
        Убирает последний слеш, оставляет первый
        """
        return os.sep + path.strip(os.sep)

    @classmethod
    def add_system_volume(cls, path: str):
        """
        Добавляет /Volumes/Macintosh HD (или иное имя системного диска),
        если директория локальная - т.е. начинается с /Users/Username/...
        """
        if path.startswith(os.path.expanduser("~")):
            return Utils.get_system_volume() + path
        return path
    
    @classmethod
    def fix_path_prefix(cls, path: str):
        """
        Устраняет проблему с изменяющимся префиксом пути к сетевому диску,
        например:   
        /Volumes/Shares/Studio/MIUZ/file.txt    
        /Volumes/Shares-1/Studio/MIUZ/file.txt  
        Приводит путь к универсальному виду и ищет актуальный том, в котором существует файл.
        """
        path = Utils.normalize_slash(path)
        splited = path.split(os.sep)[3:]
        path = os.path.join(os.sep, *splited)

        for entry in os.scandir(os.sep + Static.VOLUMES):
            new_path = entry.path + path
            if os.path.exists(new_path):
                return new_path
        return None

    @classmethod
    def get_system_volume(cls):
        """
        Возвращает путь к системному диску /Volumes/Macintosh HD (или иное имя)
        """
        # Сканируем все диски
        # Тот диск, где есть директория ApplicationSupport, является системным
        for i in os.scandir(os.sep + Static.VOLUMES):
            if os.path.exists(i.path + Static.APP_SUPPORT_APP):
                return i.path

    @classmethod
    def get_hash_filename(cls, filename: str):
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
    def get_generic_icon_path(cls, file_extension: str):
        """
        Возвращает путь к файлу svg иконки
        """
        filename = Static.SVG + "_" + file_extension.replace(".", "") + ".svg"
        return os.path.join(Static.GENERIC_ICONS_DIR, filename)

    @classmethod
    def create_generic_icon(cls, file_extension: str):
        """
        file_extension: ".jpg", ".png", и т.п.    
        Возвращает: path to svg_icon
        """
        renderer = QSvgRenderer(Static.FILE_SVG)
        width = 133
        height = 133

        # удаляем точку, делаем максимум 4 символа и капс
        # для размещения текста на иконку
        new_text = file_extension.replace(".", "")[:4].upper()
        path_to_svg = Utils.get_generic_icon_path(file_extension)

        # Создаем генератор SVG
        generator = QSvgGenerator()

        # Задаем имя файла по последней секции пути к svg
        generator.setFileName(path_to_svg)
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

        return path_to_svg

    @classmethod
    def safe_emit(cls, signal: pyqtBoundSignal, obj: object = _NULL) -> bool | None:
        try:
            if obj is Utils._NULL:
                signal.emit()
            else:
                signal.emit(obj)
            return True
        except RuntimeError:
            return None


class UThreadPool:
    pool: QThreadPool = None

    @classmethod
    def init(cls):
        cls.pool = QThreadPool.globalInstance()

    @classmethod
    def start(cls, runnable: QRunnable):
        cls.pool.start(runnable)
