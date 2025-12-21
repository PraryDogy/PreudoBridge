import subprocess
import tempfile
from pathlib import Path
import numpy as np
from PIL import Image

class PSDLoader:
    @staticmethod
    def load_as_array(psd_path: str) -> np.ndarray:
        tmp_dir = Path(tempfile.gettempdir())

        # запускаем QuickLook
        subprocess.run([
            "qlmanage", "-t", "-s", "5000", "-o", str(tmp_dir), psd_path
        ], check=True)

        # ищем созданный PNG
        generated_files = list(tmp_dir.glob(Path(psd_path).stem + "*.png"))
        if not generated_files:
            raise FileNotFoundError("QuickLook не создал PNG")
        generated = generated_files[0]

        # читаем в numpy и удаляем файл
        with Image.open(generated) as img:
            arr = np.array(img)
        generated.unlink()  # удаляем временный файл

        return arr


# пример использования
psd_path = "/Users/evlosh/Desktop/IMG_6201.psd"
arr = PSDLoader.load_as_array(psd_path)
print(arr.shape, arr.dtype)
