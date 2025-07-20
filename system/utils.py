import gc
import hashlib
import io
import os
import subprocess
import traceback

import cv2
import numpy as np
from PIL import Image
from PyQt5.QtCore import (QRect, QRectF, QRunnable, QSize, Qt, QThreadPool,
                          QTimer)
from PyQt5.QtGui import QColor, QFont, QImage, QPainter, QPixmap
from PyQt5.QtSvg import QSvgGenerator, QSvgRenderer
from PyQt5.QtWidgets import QApplication


class UImage:        
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
    def open_in_def_app(cls, path: str):
        subprocess.Popen(["open", path])

    @classmethod
    def open_in_app(cls, path: str, app_path: str):
        subprocess.Popen(["open", "-a", app_path, path])

    @classmethod
    def print_error(self):
        print()
        print("Исключение обработано.")
        print(traceback.format_exc())
        print()


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
            if self in UThreadPool.tasks:
                QTimer.singleShot(5000, lambda: self.task_fin())

    def task(self):
        raise NotImplementedError("Переопредели метод task() в подклассе.")
    
    def task_fin(self):
        UThreadPool.tasks.remove(self)
        gc.collect()


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
