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


def show_img(src):
    cv2.imshow("1", src)
    cv2.waitKey(0)


def test_psd_tools(images):
    start = time.time()

    for i in images:
        img = psd_tools.PSDImage.open(i)
        img = img.numpy(channel="color")
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        show_img(img)

    end = time.time() - start
    end = round(end, 2)

    return end


def test_PIL(images):
    start = time.time()

    for i in images:
        img = Image.open(i)
        img = np.array(img)
        # img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        show_img(img)


    end = time.time() - start
    end = round(end, 2)

    return end


from utils import ReadImage, Hash
src = "/Users/Loshkarev/Desktop/TEST IMAGES/test jpg/N01-RL723-WY1000GIA.jpg"
dest = "/Users/Loshkarev/Desktop/testttt.jpg"

img = ReadImage.read_jpg_pil(src)

show_img(img)
a = Hash.write_image_hash(output_path=dest, array_img=img)
# show_img(a)