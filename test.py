import os

def scan_current_dir(dir: str):
    for entry in os.scandir(dir):
        ...


src = "/Volumes/Shares/Studio/MIUZ/Photo/Catalog/Png/2017/07_Июль/2017-07-07(b)Кошевой"
scan_current_dir(src)