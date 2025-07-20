import os


class EvloshUtils:

    @classmethod
    def get_apps(cls, app_names: list[str]):
        """
        Возвращает на основе имен приложений:
        - {путь к приложению: имя приложения, ...}
        """
        app_dirs = [
            "/Applications",
            os.path.expanduser("~/Applications"),
            "/System/Applications"
        ]
        image_apps: dict[str, str] = {}

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
        for app_dir in app_dirs:
            if os.path.exists(app_dir):
                search_dir(app_dir)
        return image_apps