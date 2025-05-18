import os

from PyQt5.QtCore import QObject, pyqtSignal

from cfg import Static
from utils import Utils

from ._base_items import URunnable


class PathFinderSignals(QObject):
    finished_ = pyqtSignal(str)


class PathFinder(URunnable):
    volumes = "/Volumes"

    def __init__(self, path: str):
        super().__init__()
        self.signals = PathFinderSignals()
        self.path = path

    def task(self):
        result = self.get_result(self.path)
        self.signals.finished_.emit(result)

    def get_result(self, path: str) -> str | None:
        path = path.strip()
        path = path.replace("\\", os.sep)
        path = path.strip("'").strip('"') # кавычки
        path = Utils.normalize_slash(path)

        # если это локальный путь начинающийся с /Users/Username, то меняем его
        # на /Volumes/Macintosh HD/Users/Username
        sys_vol = Utils.get_system_volume(Static.APP_SUPPORT_APP)
        path = Utils.add_system_volume(path, sys_vol)

        if not path:
            return None

        splited = [i for i in path.split(os.sep) if i]
        volumes = [i.path for i in os.scandir(PathFinder.volumes)]

        # см. аннотацию add_to_start
        paths = self.add_to_start(splited, volumes)
        res = self.check_for_exists(paths)

        if res in volumes:
            return None

        elif res:
            return res
        
        else:
            # см. аннотацию метода del_from_end
            paths = [
                ended_path
                for path_ in paths
                for ended_path in self.del_from_end(path_)
            ]

            paths.sort(key=len, reverse=True)
            res = self.check_for_exists(paths)

            if res in volumes:
                return None
            
            elif res:
                return res
    
    def add_to_start(self, splited_path: list, volumes: list[str]) -> list[str]:
        """
        Пример:
        >>> splited_path = ["Volumes", "Shares-1", "Studio", "MIUZ", "Photo", "Art", "Raw", "2025"]
        >>> volumes = ["/Volumes/Shares", "/Volumes/Shares-1"]
        [
            '/Volumes/Shares/Studio/MIUZ/Photo/Art/Raw/2025',
            '/Volumes/Shares/MIUZ/Photo/Art/Raw/2025',
            '/Volumes/Shares/Photo/Art/Raw/2025',
            '/Volumes/Shares/Art/Raw/2025',
            '/Volumes/Shares/Raw/2025',
            '/Volumes/Shares/2025',
            ...
            '/Volumes/Shares-1/Studio/MIUZ/Photo/Art/Raw/2025',
            '/Volumes/Shares-1/MIUZ/Photo/Art/Raw/2025',
            '/Volumes/Shares-1/Photo/Art/Raw/2025',
            ...
        ]
        """
        new_paths = []

        for vol in volumes:

            splited_path_copy = splited_path.copy()
            while len(splited_path_copy) > 0:

                new = vol + os.sep + os.path.join(*splited_path_copy)
                new_paths.append(new)
                splited_path_copy.pop(0)

        new_paths.sort(key=len, reverse=True)
        return new_paths
    
    def check_for_exists(self, paths: list[str]) -> str | None:
        for i in paths:
            if os.path.exists(i):
                return i
        return None
    
    def del_from_end(self, path: str) -> list[str]:
        """
        Пример:
        >>> path: "/sbc01/Shares/Studio/MIUZ/Photo/Art/Raw/2025"
        [
            "/sbc01/Shares/Studio/MIUZ/Photo/Art/Raw/2025",
            "/sbc01/Shares/Studio/MIUZ/Photo/Art/Raw",
            "/sbc01/Shares/Studio/MIUZ/Photo/Art",
            "/sbc01/Shares/Studio/MIUZ/Photo",
            "/sbc01/Shares/Studio/MIUZ",
            "/sbc01/Shares/Studio",
            "/sbc01/Shares",
            "/sbc01",
        ]
        """
        new_paths = []
        while path != os.sep:
            new_paths.append(path)
            path, _ = os.path.split(path)
        return new_paths