import logging
from time import time

import numpy as np
import psd_tools
from PIL import Image

psd_tools.psd.tagged_blocks.warn = lambda *args, **kwargs: None
psd_logger = logging.getLogger("psd_tools")
psd_logger.setLevel(logging.CRITICAL)


src = "/Users/Loshkarev/Desktop/E01-MLN1360EMR.psd"


def timer(func: callable):

    def wrapper(*args, **kwargs):
        start = time()
        res = func(*args, **kwargs)
        end = round(time() - start, 3)

        return {"res": res, "timer": end}

    return wrapper


@timer
def psd_tools_test(path: str):
    img = psd_tools.PSDImage.open(fp=path)
    img = img.composite()

    if img.mode == 'RGBA':
        img = img.convert('RGB')
    
    img = np.array(img)
    return img


@timer
def pil_test(path: str):
    img = Image.open(path)
    array = np.array(img)

    return array



a: dict = psd_tools_test(src)
b: dict = pil_test(src)

print("psd tools:", a.get("timer"))
print("pil tools:", b.get("timer"))

import cv2

for i in (a, b):

    img_array = i.get("res")
    cv2.imshow("test", img_array)
    cv2.waitKey(0)