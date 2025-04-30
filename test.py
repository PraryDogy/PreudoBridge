

from PIL import Image
import tifffile
import numpy as np
import cv2

src = "/Users/Loshkarev/Downloads/3chan po kanalam.tif"
# src = "/Users/Loshkarev/Downloads/11chan po kanalam.tif"
# src = "/Users/Loshkarev/Downloads/11 chan peremez.tif"

img = tifffile.imread(src)
channels = min(img.shape)
channels_index = img.shape.index(channels)
if channels_index == 0:
    img = img.transpose(1, 2, 0)
if channels > 3:
    img = img[:, :, :3]
if str(object=img.dtype) != "uint8":
    img = (img / 256).astype(dtype="uint8")
cv2.imshow("123", img)
cv2.waitKey(0)