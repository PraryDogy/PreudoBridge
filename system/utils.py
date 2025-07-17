import hashlib
import io
import logging
import os
import subprocess
import traceback
from datetime import datetime, timedelta

import cv2
import numpy as np
import psd_tools
import rawpy
import rawpy._rawpy
import tifffile
from imagecodecs.imagecodecs import DelayedImportError
from PIL import Image
from PyQt5.QtCore import QRect, QRectF, QRunnable, QSize, Qt, QThreadPool
from PyQt5.QtGui import QColor, QFont, QImage, QPainter, QPixmap
from PyQt5.QtSvg import QSvgGenerator, QSvgRenderer
from PyQt5.QtWidgets import QApplication

from cfg import JsonData, Static

psd_tools.psd.tagged_blocks.warn = lambda *args, **kwargs: None
psd_logger = logging.getLogger("psd_tools")
psd_logger.setLevel(logging.CRITICAL)


class UImage:

    @classmethod
    def _read_tiff(cls, path: str) -> np.ndarray | None:
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
            Utils.print_error()
            try:
                img = Image.open(path)
                img = img.convert("RGB")
                array_img = np.array(img)
                img.close()
                return array_img
            except Exception as e:
                Utils.print_error()
                return None
                    
    @classmethod
    def _read_psb(cls, path: str):
        try:
            img = psd_tools.PSDImage.open(path)
            img = img.composite()
            img = img.convert("RGB")
            array_img = np.array(img)
            return array_img
        except Exception as e:
            Utils.print_error()
            return None

    @classmethod
    def _read_png(cls, path: str) -> np.ndarray | None:
        try:
            img = Image.open(path)
            if img.mode == "RGBA":
                white_background = Image.new("RGBA", img.size, (255, 255, 255))
                img = Image.alpha_composite(white_background, img)
            img = img.convert("RGB")
            array_img = np.array(img)
            img.close()
            return array_img
        except Exception as e:
            Utils.print_error()
            return None

    @classmethod
    def _read_jpg(cls, path: str) -> np.ndarray | None:
        try:
            img = Image.open(path)
            img = img.convert("RGB")
            array_img = np.array(img)
            img.close()
            return array_img
        except Exception as e:
            Utils.print_error()
            return None

    @classmethod
    def _read_raw(cls, path: str) -> np.ndarray | None:
        try:
            # https://github.com/letmaik/rawpy
            # Извлечение встроенного эскиза/превью из RAW-файла и преобразование в изображение:
            # Открываем RAW-файл с помощью rawpy
            with rawpy.imread(path) as raw:
                # Извлекаем встроенный эскиз (thumbnail)
                thumb = raw.extract_thumb()
            # Проверяем формат извлечённого эскиза
            if thumb.format == rawpy.ThumbFormat.JPEG:
                # Если это JPEG — открываем как изображение через BytesIO
                img = Image.open(io.BytesIO(thumb.data))
                # Конвертируем в RGB (на случай, если изображение не в RGB)
                img = img.convert("RGB")
            elif thumb.format == rawpy.ThumbFormat.BITMAP:
                # Если формат BITMAP — создаём изображение из массива
                img: Image.Image = Image.fromarray(thumb.data)
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
                Utils.print_error()
            array_img = np.array(img)
            img.close()
            return array_img
        except (Exception, rawpy._rawpy.LibRawDataError) as e:
            Utils.print_error()
            return None

    @classmethod
    def _read_movie(cls, path: str, time_sec=1) -> np.ndarray | None:
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
        except Exception as e:
            Utils.print_error()
            return None

    @classmethod
    def _read_any(cls, path: str) -> np.ndarray | None:
        ...

    @classmethod
    def read_image(cls, path: str) -> np.ndarray | None:
        _, ext = os.path.splitext(path)
        ext = ext.lower()
        read_any_dict: dict[str, callable] = {}

        for i in Static.ext_psd:
            read_any_dict[i] = cls._read_psb
        for i in Static.ext_tiff:
            read_any_dict[i] = cls._read_tiff
        for i in Static.ext_raw:
            read_any_dict[i] = cls._read_raw
        for i in Static.ext_jpeg:
            read_any_dict[i] = cls._read_jpg
        for i in Static.ext_png:
            read_any_dict[i] = cls._read_png
        for i in Static.ext_video:
            read_any_dict[i] = cls._read_movie

        for i in Static.ext_all:
            if i not in read_any_dict:
                raise Exception (f"utils > ReadImage > init_read_dict: не инициирован {i}")

        fn = read_any_dict.get(ext)
        if fn:
            cls._read_any = fn
            return cls._read_any(path)
        else:
            return None
        
    @classmethod
    def bytes_to_array(cls, blob: bytes) -> np.ndarray:
        try:
            with io.BytesIO(blob) as buffer:
                image = Image.open(buffer)
                return np.array(image)
            
        except Exception as e:
            Utils.print_error()
            return None

    @classmethod
    def numpy_to_bytes(cls, img_array: np.ndarray) -> bytes:
        try:
            with io.BytesIO() as buffer:
                image = Image.fromarray(img_array)
                image.save(buffer, format="JPEG")
                return buffer.getvalue()
            
        except Exception as e:
            Utils.print_error()
            return None

    @classmethod
    def desaturate_image(cls, image: np.ndarray, factor=0.2):
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            return cv2.addWeighted(
                image,
                1 - factor,
                cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR),
                factor,
                0
            )
        except Exception as e:
            Utils.print_error()
            return image

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


class Utils:
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
    def get_f_size(cls, bytes_size: int, round_value: int = 2) -> str:
        def format_size(size: float) -> str:
            if round_value == 0:
                return str(int(round(size)))
            return str(round(size, round_value))

        if bytes_size < 1024:
            return f"{bytes_size} байт"
        elif bytes_size < pow(1024, 2):
            return f"{format_size(bytes_size / 1024)} КБ"
        elif bytes_size < pow(1024, 3):
            return f"{format_size(bytes_size / pow(1024, 2))} МБ"
        elif bytes_size < pow(1024, 4):
            return f"{format_size(bytes_size / pow(1024, 3))} ГБ"
        elif bytes_size < pow(1024, 5):
            return f"{format_size(bytes_size / pow(1024, 4))} ТБ"

    @classmethod
    def get_f_date(cls, timestamp_: int, date_only: bool = False) -> str:
        date = datetime.fromtimestamp(timestamp_).replace(microsecond=0)
        now = datetime.now()
        today = now.date()
        yesterday = today - timedelta(days=1)

        if date.date() == today:
            return f"сегодня {date.strftime('%H:%M')}"
        elif date.date() == yesterday:
            return f"вчера {date.strftime('%H:%M')}"
        else:
            return date.strftime("%d.%m.%y %H:%M")

    @classmethod
    def normalize_slash(cls, path: str):
        """
        Убирает последний слеш, оставляет первый
        """
        return os.sep + path.strip(os.sep)

    @classmethod
    def add_system_volume(cls, path: str, sys_vol: str):
        """
        Добавляет /Volumes/Macintosh HD (или иное имя системного диска),
        если директория локальная - т.е. начинается с /Users/Username/...
        sys_vol - системный диск, обычно это /Volumes/Macintosh HD
        """
        if path.startswith(os.path.expanduser("~")):
            return sys_vol + path
        return path
    
    @classmethod
    def fix_path_prefix(cls, path: str, volumes="Volumes"):
        """
        Устраняет проблему с изменяющимся префиксом пути к сетевому диску,
        например:   
        /Volumes/Shares/Studio/MIUZ/file.txt    
        /Volumes/Shares-1/Studio/MIUZ/file.txt  
        Приводит путь к универсальному виду и ищет актуальный том, в котором существует файл.
        path: Путь обязан со слешем в начале и без слеша в конца
        """
        if not path.startswith(os.sep) or path.endswith(os.sep):
            raise Exception ("путь должен начинаться со слеша и в конце быть без слеша")

        splited = path.split(os.sep)[3:]
        path = os.path.join(os.sep, *splited)

        for entry in os.scandir(os.sep + volumes):
            new_path = entry.path + path
            if os.path.exists(new_path):
                return new_path
        return None

    @classmethod
    def get_system_volume(cls, app_support: str, volumes="Volumes"):
        """
        Возвращает путь к системному диску /Volumes/Macintosh HD (или иное имя)
        app_support: /Volumes/Macintosh HD/..../ApplicationSupport/current app_name
        """
        # Сканируем все диски
        # Тот диск, где есть директория ApplicationSupport, является системным
        for i in os.scandir(os.sep + volumes):
            if os.path.exists(i.path + app_support):
                return i.path

    @classmethod
    def get_hash_filename(cls, filename: str):
        return hashlib.md5(filename.encode('utf-8')).hexdigest()
    
    @classmethod
    def get_partial_hash(cls, file_path: str):
        try:
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
        except OSError as e:
            cls.print_error()
            return "partial hash error"

    @classmethod
    def get_generic_icon_path(cls, ext: str, generic_icons_dir: str):
        """
        Возвращает путь к файлу svg иконки
        ext: расширение файла .jpeg, ...
        generic_icons_dir: папка с иконками
        """
        if "." in ext:
            new_ext = ext.replace(".", "_")
        else:
            new_ext = f"_{ext}"
        filename = f"{new_ext}.svg"
        return os.path.join(generic_icons_dir, filename)

    @classmethod
    def create_generic_icon(cls, file_extension: str, icon_path: str, svg_file_path: str):
        """
        file_extension: ".jpg", ".png", и т.п.
        svg_file_path: путь к стандартной svg иконке без текста
        Возвращает: path to svg_icon
        """
        renderer = QSvgRenderer(svg_file_path)
        width = 133
        height = 133

        # удаляем точку, делаем максимум 4 символа и капс
        # для размещения текста на иконку
        new_text = file_extension.replace(".", "")[:4].upper()

        # Создаем генератор SVG
        generator = QSvgGenerator()

        # Задаем имя файла по последней секции пути к svg
        generator.setFileName(icon_path)
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

        return icon_path

    @classmethod
    def get_image_apps(cls):
        """
        Возвращает:
        - {путь к приложению: имя приложения, ...}
        """
        app_dirs = [
            "/Applications",
            os.path.expanduser("~/Applications"),
            "/System/Applications"
        ]
        image_apps: dict[str, str] = {}

        def search_dir(directory):
            try:
                for entry in os.scandir(directory):
                    if entry.name.endswith(".app"):
                        name_lower = entry.name.lower()
                        if any(k in name_lower for k in JsonData.image_apps):
                            image_apps[entry.path] = entry.name
                    elif entry.is_dir():
                        search_dir(entry.path)
            except PermissionError:
                pass
        for app_dir in app_dirs:
            if os.path.exists(app_dir):
                search_dir(app_dir)
        return image_apps
    
    @classmethod
    def open_in_def_app(cls, path: str):
        subprocess.Popen(["open", path])

    @classmethod
    def open_in_app(cls, path: str, app_path: str):
        subprocess.Popen(["open", "-a", app_path, path])

    @classmethod
    def print_error(self):
        print()
        print(traceback.format_exc())
        print()


class FitImg:   
    @classmethod
    def start(cls, image: np.ndarray, size: int) -> np.ndarray | None:
        try:
            return cls.fit_image(image, size)
        except Exception as e:
            Utils.print_error()
            return None

    @classmethod
    def fit_image(cls, image: np.ndarray, size: int) -> np.ndarray:
        h, w = image.shape[:2]
        if w > h:  # Горизонтальное изображение
            new_w = size
            new_h = int(h * (size / w))
        elif h > w:  # Вертикальное изображение
            new_h = size
            new_w = int(w * (size / h))
        else:  # Квадратное изображение
            new_w, new_h = size, size
        return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)


class URunnable(QRunnable):
    def __init__(self):
        """
        Переопределите метод task().
        Не переопределяйте run().
        """
        super().__init__()
        self.should_run__ = True
        self.finished__ = False

    def is_should_run(self):
        return self.should_run__
    
    def set_should_run(self, value: bool):
        self.should_run__ = value

    def set_finished(self, value: bool):
        self.finished__ = value

    def is_finished(self):
        return self.finished__
    
    def run(self):
        try:
            self.task()
        finally:
            self.set_finished(True)
            # if self in UThreadPool.tasks:
                # QTimer.singleShot(5000, lambda: self.task_fin())

    def task(self):
        raise NotImplementedError("Переопредели метод task() в подклассе.")
    
    # def task_fin(self):
    #     UThreadPool.tasks.remove(self)
    #     gc.collect()


class UThreadPool:
    pool: QThreadPool = None
    tasks: list[URunnable] = []

    @classmethod
    def init(cls):
        cls.pool = QThreadPool.globalInstance()

    @classmethod
    def start(cls, runnable: QRunnable):
        # cls.tasks.append(runnable)
        cls.pool.start(runnable)
