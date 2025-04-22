from pathlib import Path

src = "/Volumes/Shares/Studio/MIUZ/Photo/Art/Raw/2024/soft/Outline.app"



p = Path(src)
is_dir = p.is_dir()
is_file = p.is_file()

print(is_dir, is_file)