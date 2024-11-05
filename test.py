from utils import Utils
from PIL import Image
import cv2
import numpy as np

src = "/Users/Loshkarev/Desktop/lwz test/R2018-RL-0124.tif"
# img: Image = Image.open(src)
# img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

img  = Utils.read_image(src)

# Отобразить изображение
cv2.imshow("Image", img)
cv2.waitKey(0)
cv2.destroyAllWindows()