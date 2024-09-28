import cv2
import numpy as np
import psd_tools
import tifffile


class ImageUtils:

    @staticmethod
    def read_tiff(src: str) -> np.ndarray:
        try:
            img = tifffile.imread(files=src)[:,:,:3]
            if str(object=img.dtype) != "uint8":
                img = (img/256).astype(dtype="uint8")
            return img
        except Exception as e:
            print("tifffle error:", e, src)
            return None

    @staticmethod
    def read_psd(src: str) -> np.ndarray:
        try:
            img = psd_tools.PSDImage.open(fp=src)
            print("image opened")
            img = img.composite()
            print("image composited")

            if img.mode == 'RGBA':
                img = img.convert('RGB')
            
            img = np.array(img)
            return img

        except Exception as e:
            print("psd tools error:", e, src)
            return None
            
    @staticmethod
    def read_jpg(path: str) -> np.ndarray:
        image = cv2.imread(path, cv2.IMREAD_UNCHANGED)  # Чтение с альфа-каналом
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        if image is None:
            print("Ошибка загрузки изображения")
            return None

        return image
        
    @staticmethod
    def read_png(path: str) -> np.ndarray:
        image = cv2.imread(path, cv2.IMREAD_UNCHANGED)  # Чтение с альфа-каналом

        if image is None:
            return None

        if image.shape[2] == 4:
            alpha_channel = image[:, :, 3] / 255.0
            rgb_channels = image[:, :, :3]
            background_color = np.array([255, 255, 255], dtype=np.uint8)
            background = np.full(rgb_channels.shape, background_color, dtype=np.uint8)
            converted = (rgb_channels * alpha_channel[:, :, np.newaxis] + background * (1 - alpha_channel[:, :, np.newaxis])).astype(np.uint8)
        else:
            converted = image

        return converted