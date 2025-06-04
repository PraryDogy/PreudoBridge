import os

class PathFinder:
    volumes_dir: str = "/Volumes"
    users_dir: str = "/Users"

    def __init__(self, input_path: str):
        super().__init__()
        self.input_path: str = input_path
        self.result: str | None = None

        self.volumes_list: list[str] = self.get_volumes()
        self.macintosh_hd: str = self.get_sys_volume()
        self.volumes_list.remove(self.macintosh_hd)

        # /Volumes/Macintosh HD/Volumes
        self.invalid_volume_path: str = self.macintosh_hd + self.volumes_dir

    def get_result(self) -> str | None:
        input_path = self.prepare_path(self.input_path)

        if input_path.startswith((self.users_dir, self.macintosh_hd)):
            if input_path.startswith(self.users_dir):
                input_path = self.macintosh_hd + input_path
            input_path = self.replace_username(input_path)

            # для threading
            self.result = input_path
            return input_path

        paths = self.add_to_start(input_path)

        paths.sort(key=len, reverse=True)
        result = self.check_for_exists(paths)

        if not result:
            paths = {
                p
                for base in paths
                for p in self.del_from_end(base)
            }
            paths = sorted(paths, key=len, reverse=True)

            if self.volumes_dir in paths:
                paths.remove(self.volumes_dir)
            result = self.check_for_exists(paths)

        # для threading
        self.result = result or None
        return result or None

    def replace_username(self, path: str) -> str:
        home = os.path.expanduser("~")  # например: /Users/actual_user
        user = home.split(os.sep)[-1]   # извлекаем имя пользователя

        parts = path.split(os.sep)
        try:
            users_index = parts.index("Users")
            parts[users_index + 1] = user
            return os.sep.join(parts)
        except (ValueError, IndexError):
            return path

    def check_for_exists(self, path_list: list[str]) -> str | None:
        for path in path_list:
            if not os.path.exists(path):
                continue
            if path in self.volumes_list or path == self.invalid_volume_path:
                continue
            return path
        return None
            
    def get_volumes(self) -> list[str]:
        return [
            entry.path
            for entry in os.scandir(self.volumes_dir)
            if entry.is_dir()
        ]
    
    def get_sys_volume(self):
        user = os.path.expanduser("~")
        app_support = f"{user}/Library/Application Support"

        for i in self.volumes_list:
            full_path = f"{i}{app_support}"
            if os.path.exists(full_path):
                return i
        return None

    def prepare_path(self, path: str):
        path = path.strip().strip("'\"")
        path = path.replace("\\", "/")
        path = path.strip("/")
        return "/" + path

    def add_to_start(self, path: str) -> list[str]:
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
        for vol in self.volumes_list:
            chunk_list_copy = chunk_list.copy()
            while len(chunk_list_copy) > 0:
                new = vol + os.sep + os.path.join(*chunk_list_copy)
                new_paths.append(new)
                chunk_list_copy.pop(0)
        return new_paths
        
    def del_from_end(self, path: str) -> list[str]:
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
