from system.shared_utils import ReadImage
import cv2
import pillow_heif
pillow_heif.register_heif_opener()
from PIL import Image

img = "/Users/evlosh/Desktop/IMG_7285.jpeg"
a = Image.open(img)
a.show()