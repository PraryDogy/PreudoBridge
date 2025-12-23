import glob
import hashlib
import inspect
import os
import plistlib
import subprocess
import traceback
from datetime import datetime

import cv2
import numpy as np
from AppKit import NSBitmapImageRep, NSBundle, NSPNGFileType, NSWorkspace
from PIL import Image
from PyQt5.QtCore import QRect, QRectF, QSize, Qt
from PyQt5.QtGui import QColor, QFont, QIcon, QImage, QPainter
from PyQt5.QtSvg import QSvgGenerator, QSvgRenderer
from PyQt5.QtWidgets import QApplication

from cfg import Dynamic, Static


class Utils:
    _ws = NSWorkspace.sharedWorkspace()

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
    def get_uti_type(cls, filepath: str):
        uti_filetype, _ = Utils._ws.typeOfFile_error_(filepath, None)
        return uti_filetype
    
    @classmethod
    def get_uti_bytes_img(cls, filepath: str):
        icon = Utils._ws.iconForFile_(filepath)
        tiff = icon.TIFFRepresentation()
        rep = NSBitmapImageRep.imageRepWithData_(tiff)
        png = rep.representationUsingType_properties_(NSPNGFileType, None)
        return bytes(png)
        
    @classmethod
    def get_uti_bytes_hash(cls, filepath: str):
        icon = Utils._ws.iconForFile_(filepath)
        tiff_bytes = icon.TIFFRepresentation()[:-1].tobytes()
        return hashlib.md5(tiff_bytes).hexdigest()
    
    @classmethod
    def get_uti_error_icon(cls):
        uti_filetype_ = "public.data"
        return "public.data", Dynamic.uti_data[uti_filetype_]

    @classmethod
    def set_uti_data(cls, uti_filetype: str, qimage: QImage, size: int = 512):
        Dynamic.uti_data[uti_filetype] = {}
        for i in Static.image_sizes:
            resized_qimage = Utils.scaled(qimage, i)
            Dynamic.uti_data[uti_filetype][i] = resized_qimage
        Dynamic.uti_data[uti_filetype]["src"] = Utils.scaled(qimage, size)

    @classmethod
    def uti_generator(cls, filepath: str, size: int = 512):
        """
        Возвращает uti filetype, {image_size: QImage, image_size: QImage, }
        image_size ссылается на Static.image_sizes, то есть будет возвращен
        словарик с QImage, соответвующий всем размерам из Static.image_sizes
        """


        uti_filetype = cls.get_uti_type(filepath)

        # if uti_filetype == "public.symlink":
        #     appkit_hash = cls.get_uti_bytes_hash(filepath)
        #     if appkit_hash in Dynamic.uti_data:
        #         return appkit_hash, Dynamic.uti_data[appkit_hash]
            
        #     bytes_icon = cls.get_uti_bytes_img(filepath)
        #     qimage = QImage()
        #     qimage.loadFromData(bytes_icon)
        #     cls.set_uti_data(appkit_hash, qimage)

        #     uti_png_icon_path = os.path.join(Static.external_uti_dir, f"{appkit_hash}.png")
        #     if not os.path.exists(uti_png_icon_path):
        #         qimage = QImage.fromData(bytes_icon)
        #         qimage = Utils.scaled(qimage, size)
        #         qimage.save(uti_png_icon_path, "PNG")
        #     return appkit_hash, Dynamic.uti_data[appkit_hash]
        
        if uti_filetype == "com.apple.application-bundle":
            bundle = NSBundle.bundleWithPath_(filepath).bundleIdentifier()

            if bundle in Dynamic.uti_data:
                return bundle, Dynamic.uti_data[bundle]

            bytes_icon = cls.get_uti_bytes_img(filepath)
            qimage = QImage()
            qimage.loadFromData(bytes_icon)
            cls.set_uti_data(bundle, qimage)

            uti_png_icon_path = os.path.join(Static.external_uti_dir, f"{bundle}.png")
            if not os.path.exists(uti_png_icon_path):
                qimage = QImage.fromData(bytes_icon)
                qimage = Utils.scaled(qimage, size)
                qimage.save(uti_png_icon_path, "PNG")

            return bundle, Dynamic.uti_data[bundle]

        if not uti_filetype:
            return cls.get_uti_error_icon()

        if uti_filetype in Dynamic.uti_data:
            return uti_filetype, Dynamic.uti_data[uti_filetype]

        uti_png_icon_path = os.path.join(Static.external_uti_dir, f"{uti_filetype}.png")

        if not os.path.exists(uti_png_icon_path):
            bytes_icon = cls.get_uti_bytes_img(filepath)

            qimage = QImage.fromData(bytes_icon)
            qimage = Utils.scaled(qimage, size)
            qimage.save(uti_png_icon_path, "PNG")

        qimage = QImage(uti_png_icon_path)
        if qimage.isNull():
            return cls.get_uti_error_icon()

        set_uti_data(uti_filetype, qimage)
        return uti_filetype, Dynamic.uti_data[uti_filetype]
        
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