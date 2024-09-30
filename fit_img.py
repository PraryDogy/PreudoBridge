import cv2
from PIL import Image
import numpy as np

class FitImg:
    # @staticmethod
    # def fit(img: Image.Image, w: int, h: int) -> Image.Image:
    #     imw, imh = img.size

    #     if -3 < imw - imh < 3:
    #         imw, imh = imw, imw

    #     if w > h:

    #         if imw > imh:
    #             delta = imw/imh
    #             neww, newh = w, int(w/delta)
    #         else:
    #             delta = imh/imw
    #             neww, newh = int(h/delta), h
        
    #     else:

    #         if imw > imh:
    #             delta = imw/imh
    #             neww, newh = w, int(w/delta)
    #         else:
    #             delta = imh/imw
    #             neww, newh = int(h/delta), h

    #     return img.resize((neww, newh))
    
    @staticmethod
    def start(image: np.ndarray, size: int) -> np.ndarray | None:
        try:

            h, w = image.shape[:2]

            if w > h:  # Горизонтальное изображение
                new_w = size
                new_h = int(h * (size / w))
            elif h > w:  # Вертикальное изображение
                new_h = size
                new_w = int(w * (size / h))
            else:  # Квадратное изображение
                new_w, new_h = size, size

            return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)

        except Exception as e:
            print(e)
            return None