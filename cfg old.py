import json
import os
from datetime import date


class Config:
    app_name = "PseudoBridge"
    app_ver = "1.0.0"
    json_file = os.path.join(os.path.expanduser('~'), 'Desktop', 'cfg.json')
    db_file = os.path.join(os.path.expanduser('~'), 'Desktop', 'db.db')
    image_apps: dict = {}
    img_size = 210
    
    color_filters: list = []
    rating_filter: int = 0

    colors = {
        "\U0001F534": "Красный",
        "\U0001F535": "Синий",
        "\U0001F7E0": "Оранжевый",
        "\U0001F7E1": "Желтый",
        "\U0001F7E2": "Зеленый",
        "\U0001F7E3": "Фиолетовый",
        "\U0001F7E4": "Коричневый"
        }

    colors_order = list(colors.keys())

    img_ext: tuple = (
        ".jpg", "jpeg", "jfif",
        ".tif", ".tiff",
        ".psd", ".psb",
        ".png",
        ".nef", ".cr2", ".cr3", ".arw", ".raf"
        )

    json_data: dict = {
        "root": "/Volumes",
        "ww": 1050,
        "hh": 700,
        "ww_im": 700,
        "hh_im": 500,
        "sort": "name",
        "reversed": False,
        "extra_paths": ["/Studio/PANACEA", "/Studio/MIUZ"],
        "favs": {},
        "list_view": True,
        "clear_db": 5,
        "tab_bar": 1
        }

    @staticmethod
    def load_json_data() -> dict:
        if os.path.exists(Config.json_file):

            with open(Config.json_file, 'r') as f:
                try:
                    json_data = json.load(f)
                    json_data = Config.sync_json(json_data)
                    Config.json_data = json_data
                except json.JSONDecodeError:
                    print("Ошибка чтения json")

        else:
            with open(Config.json_file, 'w') as f:
                json.dump(Config.json_data, f, indent=4, ensure_ascii=False)

    @staticmethod
    def write_config() -> bool:
        try:
            with open(Config.json_file, 'w') as f:
                json.dump(Config.json_data, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            return False

    @staticmethod
    def sync_json(json_data: dict):
        keys_to_remove = [
            key 
            for key in json_data
            if key not in Config.json_data
            ]

        for key in keys_to_remove:
            print(f"Лишний ключ в json файле: {key}")
            del json_data[key]

        for key, default_value in Config.json_data.items():
            if key not in json_data:
                print(f"Недостающий ключ в json файле: {key}")
                json_data[key] = default_value
            elif not isinstance(json_data[key], type(default_value)):
                print(f"Несовпадающий тип значения в json файле: {key}")
                json_data[key] = default_value

        return json_data

    @staticmethod
    def find_img_apps():
        root_path = "/Applications"

        names = [
            f"Adobe Photoshop CC {i}"
            for i in range(2014, 2020)
            ]
        names.extend([
                f"Adobe Photoshop {i}"
                for i in range(2020, date.today().year + 1)
                ])
        names.append("Capture One")
        names_app = [i + ".app" for i in names]
        Config.image_apps["Просмотр"] = "/System/Applications/Preview.app"

        for item in os.listdir(root_path):
            full_path = os.path.join(root_path, item)
            app_folder = any(x for x in names if item in x)
            app_app = any(x for x in names_app if item in x)

            if app_folder:        
                app_inside_folder = os.path.join(full_path, item + ".app")
                if os.path.exists(app_inside_folder):
                    Config.image_apps[item] = app_inside_folder

            elif app_app:
                item = item.replace(".app", "")
                Config.image_apps[item] = full_path


Config.load_json_data()
Config.find_img_apps()
