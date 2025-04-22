from pathlib import Path

src = "/Volumes/Shares/Studio/MIUZ/Photo/Art/Raw/2024/soft/Outline.app"



p = Path(src)
is_dir = p.is_dir()
is_file = p.is_file()

print(is_dir, is_file)



import os
import stat

mode = os.stat(src).st_mode
is_dir = stat.S_ISDIR(mode)
is_file = stat.S_ISREG(mode)
print(is_dir, is_file)

c = os.path.splitext(src)

print(c)