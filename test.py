import os
import logging
from time import time
import numpy as np
import psd_tools
import tifffile
from PIL import Image

# Отключение предупреждений от psd_tools
psd_tools.psd.tagged_blocks.warn = lambda *args, **kwargs: None
psd_logger = logging.getLogger("psd_tools")
psd_logger.setLevel(logging.CRITICAL)

# Декоратор для измерения времени выполнения функции
def timer(func: callable):
    def wrapper(*args, **kwargs):
        start = time()
        res = func(*args, **kwargs)
        end = round(time() - start, 3)
        return {"res": res, "timer": end}
    return wrapper

# Функция для работы с psd-tools
@timer
def psd_tools_test(path: str):
    img = psd_tools.PSDImage.open(fp=path)
    img = img.composite()
    if img.mode == 'RGBA':
        img = img.convert('RGB')
    img = np.array(img)
    return img

# Функция для работы с PIL
@timer
def pil_test(path: str):
    img = Image.open(path)
    array = np.array(img)
    return array

# Функция для работы с tifffile
@timer
def read_tiff(path: str) -> np.ndarray | None:
    img = tifffile.imread(files=path)[:, :, :3]
    if str(object=img.dtype) != "uint8":
        img = (img / 256).astype(dtype="uint8")
    return img


# Итерация по файлам в директории
def process_files(src: str):
    psd_time = 0
    pil_psd_time = 0
    pil_tiff_time = 0
    tif_time = 0

    for filename in os.listdir(src):
        file_path = os.path.join(src, filename)
        
        try:

            # PSD # PSD # PSD # PSD # PSD # PSD # PSD # PSD # PSD # PSD
            if filename.lower().endswith(('.psd', '.psb')):

                continue

                # result_psd = psd_tools_test(file_path)
                # psd_time += result_psd["timer"]
                
                # result_pil = pil_test(file_path)
                # pil_psd_time += result_pil["timer"]
            

            # TIFF # TIFF # TIFF # TIFF # TIFF # TIFF # TIFF # TIFF 
            elif filename.lower().endswith('.tiff', '.tif'):
                result_tiff = read_tiff(file_path)
                tif_time += result_tiff["timer"]
                
                result_pil = pil_test(file_path)
                pil_tiff_time += result_pil["timer"]

        except Exception as e:
            print(e)
            continue

    print(f"Total time for PSD/PSB (psd-tools): {psd_time} seconds")
    print(f"Total time for PIL: {pil_psd_time} seconds")

    print()

    print(f"Total time for TIFF (tifffile): {tif_time} seconds")
    print(f"Total time for PIL: {pil_tiff_time} seconds")


# src = "/Volumes/Shares/Studio/MIUZ/Photo/Art/Ready/22 Millenium/1 IMG"
src = "/Volumes/Shares/Studio/MIUZ/Photo/Art/Ready/4 Royal/1 IMG"
process_files(src)
