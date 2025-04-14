import os
from utils import Utils
from cfg import Static

src = "/Volumes/Shares-1/Studio/MIUZ/Photo/Art/Raw/2025/04 - Апрель/2025-04-02 21-02-01.tif"


class Test:
    @classmethod
    def find_new_volume(cls, path: str):
        # Устраняет проблему с изменяющимся префиксом пути к сетевому диску,
        # например:
        #   /Volumes/Shares/Studio/MIUZ/file.txt
        #   /Volumes/Shares-1/Studio/MIUZ/file.txt
        # Приводит путь к универсальному виду и ищет актуальный том, в котором существует файл.
        path = Utils.normalize_slash(path)
        splited = path.split(os.sep)[3:]
        path = os.path.join(os.sep, *splited)

        for entry in os.scandir(os.sep + Static.VOLUMES):
            new_path = entry.path + path
            if os.path.exists(new_path):
                return new_path
        return None



a = Test.find_new_volume(src)
print(a)