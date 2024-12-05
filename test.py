import os

import numpy as np
from PIL import Image
import psd_tools
import time
import logging

psd_tools.psd.tagged_blocks.warn = lambda *args, **kwargs: None
psd_logger = logging.getLogger("psd_tools")
psd_logger.setLevel(logging.CRITICAL)

src = "/Users/Loshkarev/Desktop/PSD"

images = [
    os.path.join(src, i)
    for i in os.listdir(src)
]


def psd_tools_time(images):
    start = time.time()

    for i in images:

        img = psd_tools.PSDImage.open(fp=i)
        img = img.composite()
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


a = psd_tools_time(images)
b = PIL_time(images)

print(a)
print(b)