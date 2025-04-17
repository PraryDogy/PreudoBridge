import os


src = "/Volumes/Shares-1/Studio/MIUZ/Photo/Art/Raw/2025/04 - Апрель/Серьги для красного цветка"

from utils import Utils
test = os.stat(src)
print(Utils.get_f_date(test.st_mtime))
print(Utils.get_f_date(test.st_birthtime))