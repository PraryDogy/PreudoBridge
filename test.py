

from PIL import Image
import tifffile
import numpy as np
import cv2

src = "/Users/Loshkarev/Downloads/test.tif"
# src = "/Users/Loshkarev/Desktop/R01-MLN1637OV.tif"

img = tifffile.imread(src)
img = img.transpose(1, 2, 0)
# print(img.shape, img.dtype)

# img = np.ndarray(img)

cv2.imshow("123", img)
cv2.waitKey(0)