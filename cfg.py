import json
import os


class Config:
    json_file = os.path.join(os.path.expanduser('~'), 'Desktop', 'last_place.json')
    db_file = os.path.join(os.path.expanduser('~'), 'Desktop', 'preudo_db.db')
    json_data: dict = {}
    thumb_size = 210
    img_viewer_images: dict = {}
    img_ext: tuple = (".jpg", "jpeg", ".tif", ".tiff", ".psd", ".psb", ".png")

    @staticmethod
    def load_json_data() -> dict:
        if os.path.exists(Config.json_file):

            with open(Config.json_file, 'r') as f:
                try:

                    Config.json_data = json.load(f)
                    defs = Config.defaults()

                    if not Config.json_data.keys() == defs.keys():
                        Config.json_data = Config.defaults()
                        print("Ключи json не соответствуют ожидаемым")
                    
                    for k, v in Config.json_data.items():
                        if type(v) != type(defs[k]):
                            Config.json_data = Config.defaults()
                            print("Значения типов json не соответствуют ожидаемым")
                            break

                except json.JSONDecodeError:
                    print("Ошибка чтения json")
                    Config.json_data = Config.defaults()

        else:
            with open(Config.json_file, 'w') as f:
                Config.json_data = Config.defaults()
                json.dump(Config.json_data, f, indent=4, ensure_ascii=False)

    @staticmethod
    def defaults():
        return {
                "root": "/Volumes",
                "ww": 1050,
                "hh": 700,
                "ww_im": 400,
                "hh_im": 300,
                "sort": "name",
                "reversed": False,
                "extra_paths": ["/Studio/PANACEA", "/Studio/MIUZ"]
                }


Config.load_json_data()