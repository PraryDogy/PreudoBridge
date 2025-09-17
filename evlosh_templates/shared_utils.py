import os
from datetime import datetime, timedelta


class SharedUtils:

    @classmethod
    def get_apps(cls, app_names: list[str]):
        """
        Возвращает на основе имен приложений:
        - {путь к приложению: имя приложения, ...}
        """

        def search_dir(directory):
            try:
                for entry in os.scandir(directory):
                    if entry.name.endswith(".app"):
                        name_lower = entry.name.lower()
                        if any(k in name_lower for k in app_names):
                            image_apps[entry.path] = entry.name
                    elif entry.is_dir():
                        search_dir(entry.path)
            except PermissionError:
                pass

        app_dirs = [
            "/Applications",
            os.path.expanduser("~/Applications"),
            "/System/Applications"
        ]
        image_apps: dict[str, str] = {}
        for app_dir in app_dirs:
            if os.path.exists(app_dir):
                search_dir(app_dir)
        return image_apps

    @classmethod
    def get_sys_vol(cls):
        """
        Возвращает путь к системному диску /Volumes/Macintosh HD (или иное имя)
        """
        app_support = os.path.expanduser('~/Library/Application Support')
        volumes = "/Volumes"
        for i in os.scandir(volumes):
            if os.path.exists(i.path + app_support):
                return i.path
            
    @classmethod
    def add_sys_vol(cls, path: str, sys_vol: str):
        """
        Добавляет /Volumes/Macintosh HD (или иное имя системного диска),
        если директория локальная - т.е. начинается с /Users/Username/...
        sys_vol - системный диск, обычно это /Volumes/Macintosh HD
        """
        if path.startswith(os.path.expanduser("~")):
            return sys_vol + path
        return path
    
    @classmethod
    def norm_slash(cls, path: str):
        """
        Убирает последний слеш, оставляет первый
        """
        return os.sep + path.strip(os.sep)
                
    @classmethod
    def get_f_size(cls, bytes_size: int, round_value: int = 2) -> str:
        def format_size(size: float) -> str:
            if round_value == 0:
                return str(int(round(size)))
            return str(round(size, round_value))

        if bytes_size < 1024:
            return f"{bytes_size} байт"
        elif bytes_size < pow(1024, 2):
            return f"{format_size(bytes_size / 1024)} КБ"
        elif bytes_size < pow(1024, 3):
            return f"{format_size(bytes_size / pow(1024, 2))} МБ"
        elif bytes_size < pow(1024, 4):
            return f"{format_size(bytes_size / pow(1024, 3))} ГБ"
        elif bytes_size < pow(1024, 5):
            return f"{format_size(bytes_size / pow(1024, 4))} ТБ"

    @classmethod
    def get_f_date(cls, timestamp_: int, date_only: bool = False) -> str:
        date = datetime.fromtimestamp(timestamp_).replace(microsecond=0)
        now = datetime.now()
        today = now.date()
        yesterday = today - timedelta(days=1)

        if date.date() == today:
            return f"сегодня {date.strftime('%H:%M')}"
        elif date.date() == yesterday:
            return f"вчера {date.strftime('%H:%M')}"
        else:
            return date.strftime("%d.%m.%y %H:%M")
