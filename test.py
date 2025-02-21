import rawpy
from PIL import Image
import subprocess
import time
import numpy as np
import os

def nef_to_jpeg_sips(input_file) -> np.ndarray:

    input_dir = os.path.dirname(input_file)
    file_name = os.path.splitext(os.path.basename(input_file))[0]
    output_file = os.path.join(input_dir, f"{file_name}.jpg")

    subprocess.run(
        ["sips", "-s", "format", "jpeg", input_file, "--out", output_file],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    img = Image.open(output_file)
    img_array = np.array(img)

    try:
        os.remove(output_file)
    except os.error:
        ...
    return img_array

def nef_to_jpeg_rawpy(input_file) -> np.ndarray:
    with rawpy.imread(input_file) as raw:
        rgb = raw.postprocess()
        return np.array(rgb)

# def quicklook_to_ndarray(input_file) -> np.ndarray:
#     output_dir = os.path.dirname(input_file)
#     subprocess.run(["qlmanage", "-t", "-s", "256", "-o", output_dir, input_file])
#     img = Image.open(output_file)
#     img_array = np.array(img)
#     os.remove(output_file)
#     return img_array


src = "/Volumes/Shares/Studio/MIUZ/Photo/Art/Raw/2025/02 - Февраль/Модель/Raw"
images = []
for i in os.listdir(src):
    src_ = os.path.join(src, i)
    if os.path.isfile(src_):
        images.append(os.path.join(src, i))

images = images[:30]


# start = time.time()
# for img_ in images:
#     try:
#         quicklook_to_ndarray(input_file=img_)
#     except FileNotFoundError:
#         print(img_)
#         continue
# end = time.time() - start

# start = time.time()
# for img_ in images:
#     nef_to_jpeg_rawpy(input_file=img_)
# end_sec = time.time() - start

src = "/Users/Loshkarev/Desktop/FEB1108.NEF"
a = nef_to_jpeg_sips(src)
import cv2
cv2.imshow("123", a)
cv2.waitKey(0)