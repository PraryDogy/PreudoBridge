import io
import logging
import os
import traceback
from datetime import datetime, timedelta

import cv2
import numpy as np
import psd_tools
import rawpy
import rawpy._rawpy
import tifffile
from imagecodecs.imagecodecs import DelayedImportError
from PIL import Image, ImageOps


class SharedUtils:

    @classmethod
    def get_apps(cls, app_names: list[str]):
        """
        Возвращает на основе имен приложений:
        - {путь к приложению: имя приложения, ...}
        """

        def search_dir(directory):
            try:
                for entry in os.scandir(directory):
                    if entry.name.endswith((".app", ".APP")):
                        name_lower = entry.name.lower()
                        if any(k in name_lower for k in app_names):
                            image_apps[entry.path] = entry.name
                    elif entry.is_dir():
                        search_dir(entry.path)
            except PermissionError:
                pass

        app_dirs = [
            "/Applications",
            os.path.expanduser("~/Applications"),
            "/System/Applications"
        ]
        image_apps: dict[str, str] = {}
        for app_dir in app_dirs:
            if os.path.exists(app_dir):
                search_dir(app_dir)
        return image_apps

    @classmethod
    def get_sys_vol(cls):
        """
        Возвращает путь к системному диску /Volumes/Macintosh HD (или иное имя)
        """
        app_support = os.path.expanduser('~/Library/Application Support')
        volumes = "/Volumes"
        for i in os.scandir(volumes):
            if os.path.exists(i.path + app_support):
                return i.path
            
    @classmethod
    def add_sys_vol(cls, path: str, sys_vol: str):
        """
        Добавляет /Volumes/Macintosh HD (или иное имя системного диска),
        если директория локальная - т.е. начинается с /Users/Username/...
        sys_vol - системный диск, обычно это /Volumes/Macintosh HD
        """
        if path.startswith(os.path.expanduser("~")):
            return sys_vol + path
        return path
                    
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
    def fit_image(cls, image: np.ndarray, size: int) -> np.ndarray:

        def cmd():
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
        
        try:
            return cmd()
        except Exception as e:
            print("fit image error", e)
            return None
        
    def insert_linebreaks(text: str, n: int = 35) -> str:
        new_text = []
        for i in range(0, len(text), n):
            row = text[i:i+n]
            if row[-1] == " ":
                row = row.rstrip()
            else:
                row = row + "-"
            new_text.append(row)
        return "\n".join(new_text).rstrip("-")


class ReadImage:
    psd_tools.psd.tagged_blocks.warn = lambda *args, **kwargs: None
    psd_logger = logging.getLogger("psd_tools")
    psd_logger.setLevel(logging.CRITICAL)
    Image.MAX_IMAGE_PIXELS = None

    ext_jpeg = (
            ".jpg", ".JPG",
            ".jpeg", ".JPEG",
            ".jpe", ".JPE",
            ".jfif", ".JFIF",
            ".bmp", ".BMP",
            ".dib", ".DIB",
            ".webp", ".WEBP",
            ".ppm", ".PPM",
            ".pgm", ".PGM",
            ".pbm", ".PBM",
            ".pnm", ".PNM",
            ".gif", ".GIF",
            ".ico", ".ICO",
        )

    ext_tiff = (
        ".tif", ".TIF",
        ".tiff", ".TIFF",
    )

    ext_psd = (
        ".psd", ".PSD",
        ".psb", ".PSB",
    )

    ext_png = (
        ".png", ".PNG",
    )

    ext_raw = (
        ".nef", ".NEF",
        ".cr2", ".CR2",
        ".cr3", ".CR3",
        ".arw", ".ARW",
        ".raf", ".RAF",
        ".dng", ".DNG",
        ".rw2", ".RW2",
        ".orf", ".ORF",
        ".srw", ".SRW",
        ".pef", ".PEF",
        ".rwl", ".RWL",
        ".mos", ".MOS",
        ".kdc", ".KDC",
        ".mrw", ".MRW",
        ".x3f", ".X3F",
    )

    ext_video = (
        ".avi", ".AVI",
        ".mp4", ".MP4",
        ".mov", ".MOV",
        ".mkv", ".MKV",
        ".wmv", ".WMV",
        ".flv", ".FLV",
        ".webm", ".WEBM",
    )

    ext_icns = (
        ".icns", ".ICNS",
    )

    ext_all = (
        *ext_jpeg,
        *ext_tiff,
        *ext_psd,
        *ext_png,
        *ext_raw,
        *ext_video,
        *ext_icns,
    )

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
            print("read tiff, tifffile error", e)
            try:
                img = Image.open(path)
                img = img.convert("RGB")
                array_img = np.array(img)
                img.close()
                return array_img
            except Exception as e:
                print("read tiff, PIL error", e)
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
            print("read psb, psd tools error", e)
            return None

    @classmethod
    def _read_icns(cls, path: str):
        try:
            im = Image.open(path).convert("RGBA")  # конвертируем в RGBA
            arr = np.array(im)  # превращаем в ndarray (H, W, 4)
            return arr
        except Exception:
            print(traceback.format_exc())
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
            print("read png, PIL error", e)
            return None

    @classmethod
    def _read_jpg(cls, path: str) -> np.ndarray | None:
        try:
            img = Image.open(path)
            img = ImageOps.exif_transpose(img) 
            img = img.convert("RGB")
            array_img = np.array(img)
            img.close()
            return array_img
        except Exception as e:
            print("read jpg, PIL error", e)
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
                print("read raw, get exif error", e)
            array_img = np.array(img)
            img.close()
            return array_img
        except (Exception, rawpy._rawpy.LibRawDataError) as e:
            print("read raw error", e)
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
            print("read movie error", e)
            return None

    @classmethod
    def _read_any(cls, path: str) -> np.ndarray | None:
        ...

    @classmethod
    def read_image(cls, path: str) -> np.ndarray | None:
        _, ext = os.path.splitext(path)
        ext = ext.lower()
        read_any_dict: dict[str, callable] = {}

        for i in cls.ext_psd:
            read_any_dict[i] = cls._read_psb
        for i in cls.ext_tiff:
            read_any_dict[i] = cls._read_tiff
        for i in cls.ext_raw:
            read_any_dict[i] = cls._read_raw
        for i in cls.ext_jpeg:
            read_any_dict[i] = cls._read_jpg
        for i in cls.ext_png:
            read_any_dict[i] = cls._read_png
        for i in cls.ext_video:
            read_any_dict[i] = cls._read_movie
        for i in cls.ext_icns:
            read_any_dict[i] = cls._read_icns
        fn = read_any_dict.get(ext)
        if fn:
            cls._read_any = fn
            return cls._read_any(path)
        else:
            return None


class PathFinder:
    _volumes_dir: str = "/Volumes"
    _users_dir: str = "/Users"

    def __init__(self, input_path: str):
        super().__init__()
        self._input_path: str = input_path
        self._result: str | None = None

        self._volumes_list: list[str] = self._get_volumes()
        self._volumes_list.extend(self._get_deep_level())

        self._macintosh_hd: str = self._get_sys_volume()
        self._volumes_list.remove(self._macintosh_hd)

        # /Volumes/Macintosh HD/Volumes
        self._invalid_volume_path: str = self._macintosh_hd + self._volumes_dir

    def get_result(self) -> str | None:
        input_path = self._prepare_path(self._input_path)

        if input_path.startswith((self._users_dir, self._macintosh_hd)):
            if input_path.startswith(self._users_dir):
                input_path = self._macintosh_hd + input_path
            input_path = self._replace_username(input_path)

            # для threading
            self._result = input_path
            return input_path

        paths = self._add_to_start(input_path)

        paths.sort(key=len, reverse=True)
        result = self._check_for_exists(paths)

        if not result:
            paths = {
                p
                for base in paths
                for p in self._del_from_end(base)
            }
            paths = sorted(paths, key=len, reverse=True)

            if self._volumes_dir in paths:
                paths.remove(self._volumes_dir)
            result = self._check_for_exists(paths)

        # для threading
        self._result = result or None

        return result or None

    def _replace_username(self, path: str) -> str:
        home = os.path.expanduser("~")  # например: /Users/actual_user
        user = home.split(os.sep)[-1]   # извлекаем имя пользователя

        parts = path.split(os.sep)
        try:
            users_index = parts.index("Users")
            parts[users_index + 1] = user
            return os.sep.join(parts)
        except (ValueError, IndexError):
            return path

    def _check_for_exists(self, path_list: list[str]) -> str | None:
        for path in path_list:
            if not os.path.exists(path):
                continue
            if path in self._volumes_list:
                continue
            if path in self._invalid_volume_path:
                continue
            if self._invalid_volume_path in path:
                continue
            return path
        return None
            
    def _get_volumes(self) -> list[str]:
        return [
            entry.path
            for entry in os.scandir(self._volumes_dir)
            if entry.is_dir()
        ]
    
    def _get_deep_level(self):
        """
            Расширяет список корневых путей для поиска, добавляя промежуточные  
            уровни вложенности, чтобы учесть случаи, когда сетевой диск     
            подключён не с самого верхнего уровня.  
            Ожидаемый путь:     
            '\Studio\MIUZ\Video\Digital\Ready\2025\6. Июнь'.    
            Входящий путь:      
            '\MIUZ\Video\Digital\Ready\2025\6. Июнь'    
            Было:   
                [
                    /Volumes/Shares,
                    /Volumes/Shares-1
                ]   
            Стало:  
                [
                    /Volumes/Shares,
                    /Volumes/Shares/Studio,
                    /Volumes/Shares-1,
                    /Volumes/Shares-1/Studio
                ]
        """
        paths: list[str] = []
        for vol in self._volumes_list:
            for first_level in os.scandir(vol):
                if first_level.is_dir():
                    paths.append(first_level.path)
        return paths

    def _get_sys_volume(self):
        user = os.path.expanduser("~")
        app_support = f"{user}/Library/Application Support"

        for i in self._volumes_list:
            full_path = f"{i}{app_support}"
            if os.path.exists(full_path):
                return i
        return None

    def _prepare_path(self, path: str):
        path = path.strip("'")
        path = path.strip("\"")
        path = path.strip()
        path = path.strip("/")
        path = path.strip("\\")
        path = path.replace("\\", "/")
        return "/" + path

    def _add_to_start(self, path: str) -> list[str]:
        """
        Пример:
        >>> splited_path = ["Volumes", "Shares-1", "Studio", "MIUZ", "Photo", "Art", "Raw", "2025"]
        [
            '/Volumes/Shares/Studio/MIUZ/Photo/Art/Raw/2025',
            '/Volumes/Shares/MIUZ/Photo/Art/Raw/2025',
            '/Volumes/Shares/Photo/Art/Raw/2025',
            ...
            '/Volumes'
            '/Volumes/Shares-1/Studio/MIUZ/Photo/Art/Raw/2025',
            '/Volumes/Shares-1/MIUZ/Photo/Art/Raw/2025',
            '/Volumes/Shares-1/Photo/Art/Raw/2025',
            ...
            '/Volumes'
        ]
        """
        new_paths = []
        chunk_list = [
            i
            for i in path.split(os.sep)
            if i
        ]
        for vol in self._volumes_list:
            chunk_list_copy = chunk_list.copy()
            while len(chunk_list_copy) > 0:
                new = vol + os.sep + os.path.join(*chunk_list_copy)
                new_paths.append(new)
                chunk_list_copy.pop(0)
        return new_paths
        
    def _del_from_end(self, path: str) -> list[str]:
        """
        Пример:
        >>> path: "/sbc01/Shares/Studio/MIUZ/Photo/Art/Raw/2025"
        [
            "/sbc01/Shares/Studio/MIUZ/Photo/Art/Raw/2025",
            "/sbc01/Shares/Studio/MIUZ/Photo/Art/Raw",
            "/sbc01/Shares/Studio/MIUZ/Photo/Art",
            ...
            "/sbc01",
        ]
        """
        new_paths = []
        while path != os.sep:
            new_paths.append(path)
            path, _ = os.path.split(path)
        return new_paths
