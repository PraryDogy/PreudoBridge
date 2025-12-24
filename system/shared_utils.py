import io
import os
import signal
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import cv2
import numpy as np
import rawpy
import rawpy._rawpy
import tifffile
from PIL import Image, ImageOps


class SharedUtils:

    @classmethod
    def is_mounted(cls, server: str):
        output = subprocess.check_output(["mount"]).decode()
        return server in output
            
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
    
    @classmethod
    def exit_force(cls):
        os.kill(os.getpid(), signal.SIGKILL)


class ReadImage:
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
        def process_image(img: np.ndarray) -> np.ndarray:
            if img.ndim == 3:
                # Транспонируем, если каналы на первом месте
                if min(img.shape) == img.shape[0]:
                    img = img.transpose(1, 2, 0)
                # Ограничиваем количество каналов до 3
                if img.shape[2] > 3:
                    img = img[:, :, :3]
                # Преобразуем в uint8
                if img.dtype != np.uint8:
                    img = (img / 256).astype(np.uint8)
            elif img.ndim == 2:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            return img
        readers = (
            lambda p: tifffile.imread(p, is_ome=False),
            lambda p: np.array(Image.open(p).convert("RGB")),
            lambda p: cv2.imread(p)
        )
        for loader in readers:
            try:
                return process_image(loader(path))
            except Exception as e:
                print(f"read tiff error with {loader.__name__}: {e}")
        return None

    @classmethod
    def _read_psb(cls, path: str):
        return cls._read_quicklook(path)
        # try:
        #     img = psd_tools.PSDImage.open(path)
        #     img = img.composite()
        #     img = img.convert("RGB")
        #     array_img = np.array(img)
        #     return array_img
        # except Exception as e:
        #     print("read psb, psd tools error", e)
        #     return None
        
    @classmethod
    def _read_quicklook(cls, path: str, size: int = 5000) -> np.ndarray:
        print("load img by quicklook", path)
        tmp_dir = Path(tempfile.gettempdir())
        subprocess.run(
            ["qlmanage", "-t", "-s", str(size), "-o", str(tmp_dir), path],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL  # отключаем вывод ошибок
        )
        generated_files = list(tmp_dir.glob(Path(path).stem + "*.png"))
        if not generated_files:
            raise FileNotFoundError("QuickLook не создал PNG")
        generated = generated_files[0]
        with Image.open(generated) as img:
            arr = np.array(img)
        if os.path.exists(generated):
            generated.unlink()
        return arr

    @classmethod
    def _read_icns(cls, path: str):
        return cls._read_png(path)
        # return cls._read_quicklook(path)
        try:
            im = Image.open(path).convert("RGBA")  # конвертируем в RGBA
            arr = np.array(im)  # превращаем в ndarray (H, W, 4)
            return arr
        except Exception as e:
            # print(traceback.format_exc())
            print("read icns error", e)
            return None

    @classmethod
    def _read_png(cls, path: str) -> np.ndarray | None:
        try:
            img = Image.open(path)
            if img.mode != "RGBA":
                img = img.convert("RGBA")  # сохраняем альфа-канал
            array_img = np.array(img)
            img.close()
            return array_img
        except Exception as e:
            print("read png, PIL error", e)
            return None


    # @classmethod
    # def _read_png(cls, path: str) -> np.ndarray | None:
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
    #         print("read png, PIL error", e)
    #         return None

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
    def __init__(self, input_path: str):
        super().__init__()
        self.input_path: str = input_path
        self.mounted_disks: list[str] = self.get_mounted_disks()
        self.Macintosh_HD: str = self.get_Macintosh_HD()
        self.mounted_disks.remove(self.Macintosh_HD)

    def get_result(self):

        bad_paths: list[str] = (
            os.path.join(self.Macintosh_HD, "Volumes"),
            os.path.join(self.Macintosh_HD, "System", "Volumes")
        )

        fixed_path = self.fix_slashes(self.input_path)

        conds = (
            os.path.exists(self.input_path),
            fixed_path.startswith("/Users"),
            fixed_path.startswith(self.Macintosh_HD)
        )

        if any(conds):
            return fixed_path

        if fixed_path in bad_paths:
            return None
       
        paths = self.add_to_start(fixed_path)
        paths.sort(key=len, reverse=True)

        for i in paths:
            if os.path.exists(i):
                return i

        return None
            
    def get_mounted_disks(self) -> list[str]:
        return [
            entry.path
            for entry in os.scandir("/Volumes")
            if entry.is_dir()
        ]

    def get_Macintosh_HD(self):
        user = os.path.expanduser("~")
        app_support = f"{user}/Library/Application Support"

        for i in self.mounted_disks:
            full_path = f"{i}{app_support}"
            if os.path.exists(full_path):
                return i
        return None

    def fix_slashes(self, path: str):
        path = path.strip("'")
        path = path.strip("\"")
        path = path.strip()
        path = path.strip("/")
        path = path.strip("\\")
        path = path.replace("\\", "/")
        return "/" + path

    def add_to_start(self, path: str) -> list[str]:
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
        chunk_list = [i for i in path.split(os.sep) if i]
        for vol in self.mounted_disks:
            chunk_list_copy = chunk_list.copy()
            while len(chunk_list_copy) > 0:
                new = vol + os.sep + os.path.join(*chunk_list_copy)
                new_paths.append(new)
                chunk_list_copy.pop(0)
        return new_paths

