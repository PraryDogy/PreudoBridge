import os

def get_full_path(path):
    # Для macOS пути с /Volumes/ могут быть корректными
    return os.path.abspath(path)


a = "/Volumes/Macintosh HD/Users/Loshkarev/Desktop/0755 BG GRADIENT.psd"
b = "/Users/Loshkarev/Desktop/0755 BG GRADIENT.psd"


from utils import Utils


c = Utils.get_path_with_volumes(path=b)


print(c)