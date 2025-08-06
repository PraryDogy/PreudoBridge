import numpy as np
import cv2
import traceback

class FitImage:   

    @classmethod
    def _print_error(cls):
        print()
        print("Исключение обработано.")
        print(traceback.format_exc())
        print()

    @classmethod
    def _fit_image(cls, image: np.ndarray, size: int) -> np.ndarray:
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

    @classmethod
    def start(cls, image: np.ndarray, size: int) -> np.ndarray | None:
        try:
            return cls._fit_image(image, size)
        except Exception as e:
            # cls._print_error()
            print("Fit Image > error", e)
            return None