src = "/Volumes/Macintosh HD/Users/Loshkarev/Downloads/Фото.jfif"

from utils import Utils

a = Utils.read_image(src)

from PIL import Image
import numpy as np
# Открытие JFIF изображения
image = Image.open(src).convert("RGB")
img = np.array(image)
image.show()