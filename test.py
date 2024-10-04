import cv2
import os
import rawpy

src = "/Users/Loshkarev/Desktop/RAW"

for img in os.listdir(src):
    img = os.path.join(src, img)
    print("start read image", img)

    read = rawpy.imread(img)
    read = read.postprocess()



    cv2.imshow("23", read)
    cv2.waitKey(0)


# rawpy