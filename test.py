import rawpy
from PIL import Image
import subprocess
import time
import numpy as np
import os
import io


src = "/Users/Loshkarev/Desktop/JAN0466.NEF"


raw = rawpy.imread(src)
thumb = raw.extract_thumb()

if thumb.format == rawpy.ThumbFormat.JPEG:
    print(123)
    img = Image.open(io.BytesIO(thumb.data))

# Если миниатюра в несжатом формате (обычно это TIFF)
elif thumb.format == rawpy.ThumbFormat.BITMAP:
    print(321)
    img = Image.fromarray(thumb.data)

# Отображаем изображение
img.show()


# rgb = raw.postprocess(half_size=True, four_color_rgb=True, demosaic_algorithm=rawpy.DemosaicAlgorithm.LINEAR)
# img = Image.fromarray(rgb)
# img.show()