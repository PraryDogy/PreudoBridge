import sqlite3
import numpy as np
from PIL import Image
import io
import cv2

def bytes_to_array(blob: bytes) -> np.ndarray:
    with io.BytesIO(blob) as buffer:
        image = Image.open(buffer)
        return np.array(image)


def numpy_to_bytes(img_array: np.ndarray) -> bytes:
    with io.BytesIO() as buffer:
        image = Image.fromarray(img_array)
        image.save(buffer, format="JPEG")
        return buffer.getvalue()