import cv2
import numpy as np

class FitImg:    
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
            print("fit img error: ", e)
            return None