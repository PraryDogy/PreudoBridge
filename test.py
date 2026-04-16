import os
import subprocess
from dataclasses import dataclass
from typing import Literal

# при загрузке новой директории в main_win_item мы будем записывать
# такой mount_point как результат кода ниже

# def get_mount_and_path(path: str):
#     splited = path.strip(os.sep).split(os.sep)
#     mount, rel_path = splited[:2], splited[2:]
#     mount, rel_path = os.sep + os.sep.join(mount), os.sep + os.sep.join(rel_path)
#     return mount, rel_path


@dataclass(slots=True)
class Disk:
    type_: Literal["root", "local", "smb"]
    mount: str
    fake_name: str


class FileSystemId:

    @classmethod
    def get(cls, path: str):
        path = os.path.abspath(path)
        mounts = cls._get_mounts()
        best = None
        for device, mount_point, line in mounts:
            if path.startswith(mount_point):
                if best is None or len(mount_point) > len(best[1]):
                    best = (device, mount_point, line)
        if not best:
            return None
        device, mount_point, line = best
        if "smbfs" in line:
            return cls._parse_smb(device)
        uuid = cls._get_volume_uuid(device)
        if uuid:
            return uuid
        return None

    @classmethod
    def _get_mounts(cls):
        mounts = []
        for line in subprocess.check_output(["mount"]).decode().splitlines():
            if " on " not in line:
                continue
            device, rest = line.split(" on ", 1)
            mount_point = rest.split(" (", 1)[0]
            mounts.append((device, mount_point, line))
        return mounts

    @classmethod
    def _get_volume_uuid(cls, device):
        out = subprocess.check_output(["diskutil", "info", device]).decode()
        for line in out.splitlines():
            if "Volume UUID" in line:
                return "uuid:" + line.split(":")[1].strip()
        return None

    @classmethod
    def _parse_smb(cls, device):
        device = device.replace("//", "")
        if "@" in device:
            device = device.split("@", 1)[1]
        host, share = device.split("/", 1)
        return f"smb:{host}/{share}"
    

path = "/Users/Loshkarev/Downloads/batat4240_Minimalist_high_jewelry_still_life_two_yellow_gold_we_283a973f-4149-42c8-a52a-e004c389d78f.png"
path = "/Volumes/shares-1/Studio/MIUZ/Photo/Catalog/Ready_Premium/2026/04_Апрель/14.04.2026/R2018-RL040765ADE_2.tif"
# path = '/Volumes/Macintosh HD — данные/Library/Application Support/Uninst-3bXixkiSSZTtp7WPeXXTXV9d50U9X3KH.log'
res = FsId.get(path)
print(res)





# загружаем сетку
# по main_win_item.main_dir устанавливаем mount_point типа IP
# получается main_win_item.ip = ....

# затем мы загружаем все из finder
# создаем data item в этом же треде (не в основном потоке)
# где записываем ip, filename, rel_parent, thumb path (ip +  hash of filename + rel_parent)
# так же сюда записываем abs_path для работы с инфо / загрузкой изображения в просмотрщике копировать вставтиь
# так же мы сюда пишем какая точка монтирования, извлекаем точку из main_win_item
# так же здесь создаем qimages всех размеров (иконки)
# а еще лучше при инициации приложения создать иконки всех размеров, нам нужны иконки только папок и image


# затем идет load images
# заходим в таблицу и выделяяем строки:
# все файлы, где rel_parent == rel_parent из таблицы (то есть без /Volumes/Shares)
# все файды, где ip == ip

# как формируется thumb


# мне нужно сравнить список файлов в директории со списком файлом в базе данных
# dsta
