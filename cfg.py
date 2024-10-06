import json
import os

from PyQt5.QtWidgets import QFrame


class Config:
    app_name = "PseudoBridge"
    app_ver = "1.0.0"
    json_file = os.path.join(os.path.expanduser('~'), 'Desktop', 'cfg.json')
    db_file = os.path.join(os.path.expanduser('~'), 'Desktop', 'db.db')
    thumb_size = 210
    current_image_thumbnails: dict = {}
    selected_thumbnail: QFrame = None
    img_ext: tuple = (".jpg", "jpeg", ".tif", ".tiff", ".psd", ".psb", ".png", "jfif")

    json_data: dict = {
        "root": "/Volumes",
        "ww": 1050,
        "hh": 700,
        "ww_im": 700,
        "hh_im": 500,
        "sort": "name",
        "reversed": False,
        "extra_paths": ["/Studio/PANACEA", "/Studio/MIUZ"],
        "favs": {}
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


Config.load_json_data()