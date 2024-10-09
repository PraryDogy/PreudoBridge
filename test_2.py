from rawpy import rawpy
import os
import cv2


src = "/Users/Loshkarev/Desktop/RAW"
files = [os.path.join(src, i) for i in os.listdir(src)]

# for raw in files:
#     print(raw)
#     img = rawpy.imread(raw)
#     img = img.postprocess()
#     img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
#     cv2.imshow("1", img)
#     cv2.waitKey(0)


src = "/Users/Loshkarev/Desktop/RAW/DSC_0073.NEF"
img: rawpy.RawPy = rawpy.imread(src).postprocess()
img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)