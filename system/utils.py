import hashlib
import inspect
import os
import subprocess
import traceback
from datetime import datetime

import cv2
import numpy as np
from PIL import Image
from PyQt5.QtCore import QRect, QRectF, QSize, Qt
from PyQt5.QtGui import QColor, QFont, QImage, QPainter
from PyQt5.QtSvg import QSvgGenerator, QSvgRenderer
from PyQt5.QtWidgets import QApplication

from cfg import Dynamic, Static


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

    @classmethod
    def desaturate_image(cls, image: np.ndarray, factor=0.2):
        try:
            # если 4 канала (RGBA), убираем альфу для операции
            has_alpha = image.shape[2] == 4
            img = image[:, :, :3] if has_alpha else image

            # преобразуем в серый
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            gray_bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

            # объединяем с оригиналом
            desat = cv2.addWeighted(img, 1 - factor, gray_bgr, factor, 0)

            # если был альфа-канал, добавляем обратно
            if has_alpha:
                desat = np.dstack([desat, image[:, :, 3]])

            return desat
        except Exception:
            cls.print_error()
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
    def get_partial_hash(cls, path: str, mb: float = 0.4) -> str:
        chunk = int(mb * (1 << 20))  # переводим МБ в байты
        h = hashlib.sha256()
        with open(path, "rb") as f:
            h.update(f.read(chunk))
        return h.hexdigest()

    @classmethod
    def get_abs_thumb_path(cls, partial_hash: str) -> str:
        base = os.path.join(
            Static.external_thumbs_dir,
            partial_hash[:2],
            partial_hash[2:]
        )
        return base

    @classmethod
    def write_thumb(cls, thumb_path: str, thumb_array: np.ndarray) -> bool:
        try:
            if len(thumb_array.shape) == 2:  # grayscale
                img = thumb_array
            elif thumb_array.shape[2] == 3:  # BGR
                img = cv2.cvtColor(thumb_array, cv2.COLOR_BGR2RGB)
            elif thumb_array.shape[2] == 4:  # BGRA (с альфой)
                img = cv2.cvtColor(thumb_array, cv2.COLOR_BGRA2RGBA)  # сохраняем альфу
            else:
                print(f"write_thumb: неподдерживаемое число каналов {thumb_array.shape}")
                return False

            os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
            if thumb_array.shape[2] == 4:
                return cv2.imwrite(thumb_path, img, [cv2.IMWRITE_PNG_COMPRESSION, 3])
            else:
                return cv2.imwrite(thumb_path, img)
        except Exception as e:
            print(f"write_thumb: ошибка записи thumb на диск: {e}")
            return False

    @classmethod
    def read_thumb(cls, thumb_path: str) -> np.ndarray | None:
        try:
            if os.path.exists(thumb_path):
                img = cv2.imread(thumb_path, cv2.IMREAD_UNCHANGED)
                if img is None:
                    return None
                if len(img.shape) == 2:  # grayscale
                    return img
                elif img.shape[2] == 3:  # BGR → RGB
                    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                elif img.shape[2] == 4:  # BGRA → RGBA
                    return cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)
                else:
                    return img
            return None
        except Exception as e:
            print(f"read_thumb: ошибка чтения thumb: {e}")
            return None

        
    @classmethod
    def get_now(cls):
        return int(datetime.now().replace(microsecond=0).timestamp())
    
    @classmethod
    def get_hashdir_size(self):
        """
        !!!
        Только для QRunnable
        !!!
        Возвращает {"total": размер в байтах, "count": количество файлов}
        """
        total = 0
        count = 0
        stack = [Static.external_thumbs_dir]
        while stack:
            current = stack.pop()
            for i in os.scandir(current):
                if i.is_dir():
                    stack.append(i.path)
                elif i.name.endswith(Static.img_exts):
                    total += os.path.getsize(i.path)
                    count += 1
        return {"total": total, "count": count}

    @classmethod
    def img_to_qimg(cls, image: Image.Image) -> QImage | None:
        try:
            qimage = QImage(
                image.tobytes(),
                image.width,
                image.height,
                image.width * 4,
                QImage.Format_RGBA8888
            )
            return qimage.copy()
        except Exception:
            print(traceback.format_exc())
            return None
    
    @classmethod
    def scaled(cls, qimage: QImage, size: int, dpr: int = 2):
        scaled = qimage.scaled(
            int(size * dpr),
            int(size * dpr),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        scaled.setDevicePixelRatio(dpr)
        return scaled
    
    @classmethod
    def fill_missing_methods(cls, from_cls: callable, to_cls: callable):
        for name, func in inspect.getmembers(from_cls, inspect.isfunction):
            if not hasattr(to_cls, name):
                setattr(to_cls, name, lambda *a, **kw: None)
    
    @classmethod
    def render_svg(cls, path: str, size: int) -> QImage:
        size = QSize(size, size)
        renderer = QSvgRenderer(path)

        image = QImage(
            size,
            QImage.Format_ARGB32_Premultiplied
        )
        image.fill(Qt.transparent)

        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        renderer.render(painter)
        painter.end()

        return image