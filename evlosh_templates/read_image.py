import io
import logging
import os
import traceback

import cv2
import numpy as np
import psd_tools
import rawpy
import rawpy._rawpy
import tifffile
from imagecodecs.imagecodecs import DelayedImportError
from PIL import Image

psd_tools.psd.tagged_blocks.warn = lambda *args, **kwargs: None
psd_logger = logging.getLogger("psd_tools")
psd_logger.setLevel(logging.CRITICAL)


class ReadImage:

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

    ext_all = (
        *ext_jpeg,
        *ext_tiff,
        *ext_psd,
        *ext_png,
        *ext_raw,
        *ext_video,
    )


    @classmethod
    def _print_error():
        print()
        print("Исключение обработано.")
        print(traceback.format_exc())
        print()

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
            cls._print_error()
            try:
                img = Image.open(path)
                img = img.convert("RGB")
                array_img = np.array(img)
                img.close()
                return array_img
            except Exception as e:
                cls._print_error()
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
            cls._print_error()
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
            cls._print_error()
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
            cls._print_error()
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
                cls._print_error()
            array_img = np.array(img)
            img.close()
            return array_img
        except (Exception, rawpy._rawpy.LibRawDataError) as e:
            cls._print_error()
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
            cls._print_error()
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

        for i in cls.ext_all:
            if i not in read_any_dict:
                raise Exception (f"utils > ReadImage > init_read_dict: не инициирован {i}")

        fn = read_any_dict.get(ext)
        if fn:
            cls._read_any = fn
            return cls._read_any(path)
        else:
            return None