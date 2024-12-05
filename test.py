import os

import numpy as np
from PIL import Image
import psd_tools
import time
import cv2
import logging

psd_tools.psd.tagged_blocks.warn = lambda *args, **kwargs: None
psd_logger = logging.getLogger("psd_tools")
psd_logger.setLevel(logging.CRITICAL)

src = "/Users/Loshkarev/Desktop/PSD"
src = "/Users/Loshkarev/Desktop/test jpg"
src = "/Volumes/Shares/Studio/MIUZ/Photo/Art/Ready/1 Solo/1 IMG"

images = [
    os.path.join(src, i)
    for i in os.listdir(src)
    if i.endswith((".jpg", ".JPG", ".jpeg", ".JPEG"))
][:50]


def psd_tools_time(images):
    start = time.time()

    for i in images:

        img = cv2.imread(i, cv2.IMREAD_UNCHANGED)

    end = time.time() - start
    end = round(end, 2)

    return end


def cv_time(images):
    start = time.time()

    for i in images:
        img = Image.open(i)
        img = np.array(img)

    end = time.time() - start
    end = round(end, 2)

    return end


def PIL_time(images):
    start = time.time()

    for i in images:
        img = Image.open(i)
        img = np.array(img)

    end = time.time() - start
    end = round(end, 2)

    return end


a = cv_time(images)
b = PIL_time(images)

print(a)
print(b)