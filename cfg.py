import json
import os


class Config:
    json_file = os.path.join(os.path.expanduser('~'), 'Desktop', "Evgeny", 'last_place.json')
    db_file = os.path.join(os.path.expanduser('~'), 'Desktop', "Evgeny", 'preudo_db.db')
    json_data: dict = {}
    thumb_size = 210
    img_viewer_images: dict = {}

    @staticmethod
    def load_json_data() -> dict:
        if os.path.exists(Config.json_file):
            with open(Config.json_file, 'r') as f:
                Config.json_data = json.load(f)
        else:
            with open(Config.json_file, 'w') as f:
                Config.json_data = {
                    "root": "/Volumes",
                    "ww": 1050,
                    "hh": 700,
                    "sort": "name",
                    "reversed": False,
                    "only_photo": False,
                    "hidden_dirs": False,
                    }
                json.dump(Config.json_data, f, indent=4, ensure_ascii=False)


Config.load_json_data()