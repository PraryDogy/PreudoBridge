from utils import Utils


src = "/Users/Loshkarev/Desktop/8bit.psd"
src = "/Users/Loshkarev/Desktop/16bit.psd"
a = Utils.read_image(src)

# import cv2
# cv2.imshow("123", a)
# cv2.waitKey(0)


# with open(src, "rb") as psd_file:
#     header = psd_file.read(32)  # Читаем первые 32 байта
#     print(f"Header: {header.hex()}")  # Вывод заголовка