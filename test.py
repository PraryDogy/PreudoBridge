from PIL import Image
import struct

def get_psd_size(path):
    with open(path, "rb") as f:
        header = f.read(26)

    if header[:4] != b"8BPS":
        raise ValueError("Не PSD")

    height, width = struct.unpack(">II", header[14:22])
    return width, height

img = "/Users/evlosh/Desktop/IMG_6201.psd"
print(psd_size(img))
