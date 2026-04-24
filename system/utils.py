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
from system.shared_utils import ImgUtils


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
    def open_in_app(cls, path: str, app_path: str):
        if app_path:
            subprocess.Popen(["open", "-a", app_path, path])
        else:
            subprocess.Popen(["open", path])

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
    def create_thumb_path(cls, filename: str, mod: int, rel_parent, fs_id: str):
        """
        Создает hash:
        имя файла + дата модицикации + относительный путь к родителю + fs_id
        Создает папку при необходимости.
        fs_id: смотри system > utils > Utils > get_fs_id
        """
        string = f"{filename}{mod}{rel_parent}{fs_id}"
        hash = hashlib.md5(string.encode('utf-8')).hexdigest() + ".jpg"
        new_folder = os.path.join(Static.external_thumbs_dir, hash[:2])
        os.makedirs(new_folder, exist_ok=True)
        return os.path.join(new_folder, hash)

    @classmethod
    def write_thumb(cls, thumb_path: str, thumb_array: np.ndarray) -> bool:
        try:
            if len(thumb_array.shape) == 2:  # grayscale
                img = thumb_array
                return cv2.imwrite(thumb_path, img)
            elif thumb_array.shape[2] == 3:  # BGR
                img = cv2.cvtColor(thumb_array, cv2.COLOR_BGR2RGB)
                return cv2.imwrite(thumb_path, img)
            elif thumb_array.shape[2] == 4:  # BGRA (с альфой)
                img = cv2.cvtColor(thumb_array, cv2.COLOR_BGRA2RGBA)
                return cv2.imwrite(thumb_path, img, [cv2.IMWRITE_PNG_COMPRESSION, 3])
            else:
                print(f"write_thumb: неподдерживаемое число каналов {thumb_array.shape}")
                return False
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
    
    @classmethod
    def get_fs_id(cls, abs_path: str):
        """
        Возвращает fs_id:
        - для smb: //Loshkarev%40mjf.lan@192.168.10.121/shares
        - для локальных дисков: 59897B99-3094-42BD-9C51-56F1FF7191B6
        """

        df_res = subprocess.run(
            ["df", abs_path],
            capture_output=True,
            text=True,
            encoding="utf-8"
        )
        lines = df_res.stdout.splitlines()
        device, mp = lines[1].split()[0], lines[1].split()[-1]

        # получаем UUID
        du_res = subprocess.run(
            ["diskutil", "info", device],
            capture_output=True,
            text=True,
            encoding="utf-8"
        )

        uuid = None
        for line in du_res.stdout.splitlines():
            if "Volume UUID" in line:
                uuid = line.split(":")[1].strip()
                break

        if uuid:
            fs_id = uuid
        else:
            fs_id = device

        return fs_id

    @classmethod
    def get_rel_parent(cls, abs_path: str):
        if abs_path.startswith("/Users"):
            return abs_path
        else:
            splited = abs_path.strip(os.sep).split(os.sep)
            return os.sep + os.sep.join(splited[2:])