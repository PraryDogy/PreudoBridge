import os


class PathFinder:
    VOLUMES = os.sep + "Volumes"
    EXTRA_PATHS = [

    ]

    @classmethod
    def get_path(cls, path: str) -> str | None:
        prepared = cls.prepare_path(path=path)
        splited = cls.path_to_list(path=prepared)
        volumes = cls.get_volumes()
        started = cls.add_to_start(splited_path=splited, volumes=volumes)
        return started

    @classmethod
    def get_volumes(cls) -> list[str]:
        return [
            entry.path
            for entry in os.scandir(cls.VOLUMES)
            if entry.is_dir()
        ]
    
    @classmethod
    def prepare_path(cls, path: str) -> str:
        path = path.replace("\\", os.sep)
        path = path.strip()
        path = os.sep + path.strip(os.sep)
        return path

    @classmethod
    def path_to_list(cls, path: str) -> list[str]:
        return [
            i
            for i in path.split(os.sep)
            if i
        ]

    @classmethod
    def add_to_start(cls, splited_path: list, volumes: list[str]) -> list[str]:

        new_paths = []

        for vol in volumes:

            splited_path_copy = splited_path.copy()
            while len(splited_path_copy) > 0:

                new = vol + os.sep + os.path.join(*splited_path_copy)
                new_paths.append(new)
                splited_path_copy.pop(0)

        new_paths.sort(key=len, reverse=True)
        return new_paths
    
    @classmethod
    def check_for_exists(cls, paths: list[str]) -> str | None:
        for i in paths:
            if os.path.exists(i):
                return i
        return None

src = "/Volumes/Shares/Studio/MIUZ/Photo/Art/Raw/2025/02 - Февраль"
res = PathFinder.get_path(path=src)

for i in res:
    print(i)