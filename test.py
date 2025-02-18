import os


class PathFinder:
    VOLUMES = os.sep + "Volumes"
    EXTRA_PATHS = []

    @classmethod
    def get_path(cls, path: str) -> str | None:

        if os.path.exists(path):
            return path

        # удаляем новые строки, лишние слешы
        prepared = cls.prepare_path(path=path)

        # превращаем путь в список 
        splited = cls.path_to_list(path=prepared)

        # игнорируем /Volumes/Macintosh HD
        volumes = cls.get_volumes()[1:]

        # формируем список путей, добавляя к усеченным вариантам исходного
        # пути разные корневые тома Volumes.
        paths = cls.add_to_start(splited_path=splited, volumes=volumes)


        res = cls.check_for_exists(paths=paths)

        if res:
            return res
        
        paths = [
            ended_path
            for path_ in paths
            for ended_path in cls.del_from_end(path=path_)
        ]

        paths.sort(key=len, reverse=True)
        
        res = cls.check_for_exists(paths=paths)

        return res

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
        """
        Формирует список путей, добавляя к усеченным вариантам исходного пути разные корневые тома.

        Алгоритм работы:
        1. Для каждого элемента из volumes:
        - Создается копия splited_path.
        - Поэтапно удаляются начальные элементы splited_path
        - К splited_path добавляется элемент из Volumes 

        Пример:
        >>> splited_path = ["Volumes", "Shares-1", "Studio", "MIUZ", "Photo", "Art", "Raw", "2025"]
        >>> volumes = ["/Volumes/Shares", "/Volumes/Shares-1"]
        [
            '/Volumes/Shares/Studio/MIUZ/Photo/Art/Raw/2025',
            '/Volumes/Shares/MIUZ/Photo/Art/Raw/2025',
            '/Volumes/Shares/Photo/Art/Raw/2025',
            ...
            '/Volumes/Shares-1/Studio/MIUZ/Photo/Art/Raw/2025',
            '/Volumes/Shares-1/MIUZ/Photo/Art/Raw/2025',
            '/Volumes/Shares-1/Photo/Art/Raw/2025',
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
    
    @classmethod
    def check_for_exists(cls, paths: list[str]) -> str | None:
        for i in paths:
            if os.path.exists(i):
                return i
        return None
    
    @classmethod
    def del_from_end(cls, path: str) -> list[str]:

        new_paths = []

        while path != os.sep:
            new_paths.append(path)
            path, _ = os.path.split(path)

        return new_paths

src = "sb01/Shares/Studio/MIUZ/Photo/Art/Raw/2025/02 - Февраль"

res = PathFinder.get_path(path=src)
print()
print(res)
print()