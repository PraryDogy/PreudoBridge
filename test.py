import glob
import os

path = "/"
# test = glob.glob(os.path.join(path, '*'))

files = []


for item in os.listdir(path):
    src = os.path.join(path, item)
    
    try:
        os.listdir(src)
    except (PermissionError, NotADirectoryError, FileNotFoundError):
        continue

    try:
        stats = os.stat(item)
    except Exception:
        continue
