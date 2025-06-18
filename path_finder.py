import os

class PathFinder:
    _volumes_dir: str = "/Volumes"
    _users_dir: str = "/Users"

    def __init__(self, input_path: str):
        super().__init__()
        self._input_path: str = input_path
        self._result: str | None = None

        self._volumes_list: list[str] = self._get_volumes()
        self._volumes_list.extend(self._get_deep_level())

        self._macintosh_hd: str = self._get_sys_volume()
        self._volumes_list.remove(self._macintosh_hd)

        # /Volumes/Macintosh HD/Volumes
        self._invalid_volume_path: str = self._macintosh_hd + self._volumes_dir

    def get_result(self) -> str | None:
        input_path = self._prepare_path(self._input_path)

        if input_path.startswith((self._users_dir, self._macintosh_hd)):
            if input_path.startswith(self._users_dir):
                input_path = self._macintosh_hd + input_path
            input_path = self._replace_username(input_path)

            # для threading
            self._result = input_path
            return input_path

        paths = self._add_to_start(input_path)

        paths.sort(key=len, reverse=True)
        result = self._check_for_exists(paths)

        if not result:
            paths = {
                p
                for base in paths
                for p in self._del_from_end(base)
            }
            paths = sorted(paths, key=len, reverse=True)

            if self._volumes_dir in paths:
                paths.remove(self._volumes_dir)
            result = self._check_for_exists(paths)

        # для threading
        self._result = result or None
        return result or None

    def _replace_username(self, path: str) -> str:
        home = os.path.expanduser("~")  # например: /Users/actual_user
        user = home.split(os.sep)[-1]   # извлекаем имя пользователя

        parts = path.split(os.sep)
        try:
            users_index = parts.index("Users")
            parts[users_index + 1] = user
            return os.sep.join(parts)
        except (ValueError, IndexError):
            return path

    def _check_for_exists(self, path_list: list[str]) -> str | None:
        for path in path_list:
            if not os.path.exists(path):
                continue
            if path in self._volumes_list or path == self._invalid_volume_path:
                continue
            return path
        return None
            
    def _get_volumes(self) -> list[str]:
        return [
            entry.path
            for entry in os.scandir(self._volumes_dir)
            if entry.is_dir()
        ]
    
    def _get_deep_level(self):
        """
            Расширяет список корневых путей для поиска, добавляя промежуточные  
            уровни вложенности, чтобы учесть случаи, когда сетевой диск     
            подключён не с самого верхнего уровня.  
            Ожидаемый путь:     
            '\Studio\MIUZ\Video\Digital\Ready\2025\6. Июнь'.    
            Входящий путь:      
            '\MIUZ\Video\Digital\Ready\2025\6. Июнь'    
            Было:   
                [
                    /Volumes/Shares,
                    /Volumes/Shares-1
                ]   
            Стало:  
                [
                    /Volumes/Shares,
                    /Volumes/Shares/Studio,
                    /Volumes/Shares-1,
                    /Volumes/Shares-1/Studio
                ]
        """
        paths: list[str] = []
        for vol in self._volumes_list:
            for first_level in os.scandir(vol):
                if first_level.is_dir():
                    paths.append(first_level.path)
        return paths

    def _get_sys_volume(self):
        user = os.path.expanduser("~")
        app_support = f"{user}/Library/Application Support"

        for i in self._volumes_list:
            full_path = f"{i}{app_support}"
            if os.path.exists(full_path):
                return i
        return None

    def _prepare_path(self, path: str):
        path = path.strip().strip("'\"")
        path = path.replace("\\", "/")
        path = path.strip("/")
        return "/" + path

    def _add_to_start(self, path: str) -> list[str]:
        """
        Пример:
        >>> splited_path = ["Volumes", "Shares-1", "Studio", "MIUZ", "Photo", "Art", "Raw", "2025"]
        [
            '/Volumes/Shares/Studio/MIUZ/Photo/Art/Raw/2025',
            '/Volumes/Shares/MIUZ/Photo/Art/Raw/2025',
            '/Volumes/Shares/Photo/Art/Raw/2025',
            ...
            '/Volumes'
            '/Volumes/Shares-1/Studio/MIUZ/Photo/Art/Raw/2025',
            '/Volumes/Shares-1/MIUZ/Photo/Art/Raw/2025',
            '/Volumes/Shares-1/Photo/Art/Raw/2025',
            ...
            '/Volumes'
        ]
        """
        new_paths = []
        chunk_list = [
            i
            for i in path.split(os.sep)
            if i
        ]
        for vol in self._volumes_list:
            chunk_list_copy = chunk_list.copy()
            while len(chunk_list_copy) > 0:
                new = vol + os.sep + os.path.join(*chunk_list_copy)
                new_paths.append(new)
                chunk_list_copy.pop(0)
        return new_paths
        
    def _del_from_end(self, path: str) -> list[str]:
        """
        Пример:
        >>> path: "/sbc01/Shares/Studio/MIUZ/Photo/Art/Raw/2025"
        [
            "/sbc01/Shares/Studio/MIUZ/Photo/Art/Raw/2025",
            "/sbc01/Shares/Studio/MIUZ/Photo/Art/Raw",
            "/sbc01/Shares/Studio/MIUZ/Photo/Art",
            ...
            "/sbc01",
        ]
        """
        new_paths = []
        while path != os.sep:
            new_paths.append(path)
            path, _ = os.path.split(path)
        return new_paths
