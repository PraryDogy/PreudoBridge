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


def test_psd_tools(images):
    start = time.time()

    for i in images:
        img = psd_tools.PSDImage.open(i)
        img = img.numpy()[..., :3]
        # img = np.array(img)

        # cv2.imshow("1", img)
        # cv2.waitKey(0)

    end = time.time() - start
    end = round(end, 2)

    return end


def test_PIL(images):
    start = time.time()

    for i in images:
        img = Image.open(i)
        img = np.array(img)

    end = time.time() - start
    end = round(end, 2)

    return end


src = "/Users/Loshkarev/Desktop/TEST IMAGES/test big psd"

images = [
    os.path.join(src, i)
    for i in os.listdir(src)
    # if i.endswith((".jpg", ".JPG", ".jpeg", ".JPEG"))x
    if i.endswith((".psd", ".PSD", ".psb", ".PSB"))
][:50]


a = test_psd_tools(images)
b = test_PIL(images)

print(a)
print(b)
