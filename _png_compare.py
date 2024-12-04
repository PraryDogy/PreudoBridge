from time import time

import cv2
import numpy as np
from PIL import Image
import os

# Декоратор для измерения времени выполнения функции
def timer(func: callable):
    def wrapper(*args, **kwargs):
        start = time()
        res = func(*args, **kwargs)
        end = round(time() - start, 3)
        return {"res": res, "timer": end}
    return wrapper

@timer
def read_png_cv2(path: str) -> np.ndarray | None:
    try:
        image = cv2.imread(path, cv2.IMREAD_UNCHANGED)  # Чтение с альфа-каналом

        if image.shape[2] == 4:
            alpha_channel = image[:, :, 3] / 255.0
            rgb_channels = image[:, :, :3]
            background_color = np.array([255, 255, 255], dtype=np.uint8)
            background = np.full(rgb_channels.shape, background_color, dtype=np.uint8)
            converted = (rgb_channels * alpha_channel[:, :, np.newaxis] + background * (1 - alpha_channel[:, :, np.newaxis])).astype(np.uint8)
        else:
            converted = image

        converted = cv2.cvtColor(converted, cv2.COLOR_BGR2RGB)
        return converted
    except Exception as e:
        ...

@timer
def read_png_pil(path: str) -> np.ndarray | None:
    try:
        img = Image.open(path)

        if img.mode == "RGBA":
            white_background = Image.new("RGBA", img.size, (255, 255, 255))
            img = Image.alpha_composite(white_background, img)
            img = img.convert("RGB")

        img_array = np.array(img)

        return img_array
    except Exception as e:
        print(e)
        return None



src = "/Volumes/Shares/Studio/MIUZ/Photo/Catalog/Png_Premium"
total_cv2 = 0
total_pil = 0


for i in os.listdir(src)[:100]:

    img_src = os.path.join(src, i)

    res: dict = read_png_cv2(img_src)
    total_cv2 += res.get("timer")

    res_pil: dict = read_png_pil(img_src)
    total_pil += res_pil.get("timer")

print()
print("total cv2:", total_cv2)
print("total pil:", total_pil)
print()

# pil faster