from PIL import Image
import numpy as np
import cv2

src = "/Volumes/Shares/Studio/MIUZ/Photo/Art/Ready/1 Solo/1 IMG/R01-SOL171-025-G3.psd"

img = Image.open(src)
img = np.array(img)
img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
cv2.imshow("1", img)
cv2.waitKey(0)