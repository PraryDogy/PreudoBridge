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


class ImageUtils:        
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
    def numpy_to_bytes(cls, img_array: np.ndarray) -> bytes | None:
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
    def qimage_from_array(cls, image: np.ndarray) -> QImage | None:
        if not (isinstance(image, np.ndarray) and QApplication.instance()):
            return None
        if image.ndim == 2:  # grayscale
            height, width = image.shape
            bytes_per_line = width
            qimage = QImage(image.data, width, height, bytes_per_line, QImage.Format_Grayscale8)
        elif image.ndim == 3 and image.shape[2] in (3, 4):
            height, width, channels = image.shape
            bytes_per_line = channels * width
            fmt = QImage.Format_RGB888 if channels == 3 else QImage.Format_RGBA8888
            qimage = QImage(image.data, width, height, bytes_per_line, fmt)
        else:
            print("pixmap from array channels trouble", image.shape)
            return None
        return qimage


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
    def get_icon_path(cls, ext: str, icons_dir: str):
        return os.path.join(icons_dir, ext.lower().lstrip('.') + '.svg')

    @classmethod
    def create_icon(cls, ext: str, icon_path: str, file_svg: str):
        """
        icon_path: куда будет сохранена svg иконка
        file_svg: пустой svg, на который будет нанесен текст
        """
        renderer = QSvgRenderer(file_svg)
        width = 133
        height = 133

        # удаляем точку, делаем максимум 4 символа и капс
        # для размещения текста на иконку
        new_text = ext.replace(".", "")[:4].upper()

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
