import hashlib
import inspect
import os
import plistlib
import subprocess
import traceback
from datetime import datetime

import cv2
import numpy as np
from AppKit import NSBitmapImageRep, NSPNGFileType, NSWorkspace
from PIL import Image
from PyQt5.QtCore import QRect, QRectF, QSize, Qt, QByteArray
from PyQt5.QtGui import QColor, QFont, QIcon, QImage, QPainter, QPixmap
from PyQt5.QtSvg import QSvgGenerator, QSvgRenderer
from PyQt5.QtWidgets import QApplication

from cfg import Static, Dynamic


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
    def get_partial_hash(cls, path: str, mb: float = 0.4) -> str:
        chunk = int(mb * (1 << 20))  # переводим МБ в байты
        h = hashlib.sha256()
        with open(path, "rb") as f:
            h.update(f.read(chunk))
        return h.hexdigest()

    @classmethod
    def get_abs_thumb_path(cls, partial_hash: str) -> str:
        base = os.path.join(
            Static.thumbnails_dir,
            partial_hash[:2],
            partial_hash[2:] + ".jpg"
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
            ext = os.path.splitext(thumb_path)[1].lower()
            if ext == ".png":
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
                return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            else:
                # print(f"read_thumb: файл не существует {thumb_path}")
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
        Возвращает {"total": размер в байтах, "count": количество файлов}
        """
        total = 0
        count = 0
        stack = [Static.thumbnails_dir]
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
    def get_app_icns(cls, app_path: str):
        plist_path = os.path.join(app_path, "Contents", "info.plist")
        with open(plist_path, "rb") as f:
            plist: dict = plistlib.load(f)
        icon_name: str = plist.get("CFBundleIconFile")
        if not icon_name.endswith(".icns"):
            icon_name += ".icns"
        icns_path = os.path.join(app_path, "Contents", "Resources", icon_name)
        return icns_path
    
    @classmethod
    def qiconed_resize(cls, pixmap: QPixmap, max_side: int) -> QPixmap:
        if pixmap.isNull():
            return QPixmap()
        w, h = pixmap.width(), pixmap.height()
        if w > h:
            new_w = max_side
            new_h = int(h * max_side / w)
        else:
            new_h = max_side
            new_w = int(w * max_side / h)
        icon = QIcon(pixmap)
        return icon.pixmap(QSize(new_w, new_h))
    
    @classmethod
    def fill_missing_methods(cls, from_cls: callable, to_cls: callable):
        for name, func in inspect.getmembers(from_cls, inspect.isfunction):
            if not hasattr(to_cls, name):
                setattr(to_cls, name, lambda *a, **kw: None)

    @classmethod
    def uti_generator(cls, filepath: str) -> QImage:
        ws = NSWorkspace.sharedWorkspace()
        uti_filetype, _ = ws.typeOfFile_error_(filepath, None)

        # Проверка кэша в памяти
        if uti_filetype in Dynamic.uti_filetype_qimage:
            return Dynamic.uti_filetype_qimage[uti_filetype]

        uti_png_icon_path = os.path.join(Static.uti_icons, f"{uti_filetype}.png")

        if not os.path.exists(uti_png_icon_path):
            # Генерация иконки
            icon = ws.iconForFileType_(uti_filetype)
            tiff = icon.TIFFRepresentation()
            rep = NSBitmapImageRep.imageRepWithData_(tiff)
            png_data = rep.representationUsingType_properties_(NSPNGFileType, None)

            # Сохраняем PNG на диск
            with open(uti_png_icon_path, "wb") as f:
                f.write(png_data)

            # Создаём QImage напрямую из NSData
            qimage = QImage.fromData(QByteArray(png_data))
        else:
            # Если PNG уже есть, создаём QImage из файла
            qimage = QImage(uti_png_icon_path)

        # Кэшируем в памяти
        Dynamic.uti_filetype_qimage[uti_filetype] = qimage
        return qimage
