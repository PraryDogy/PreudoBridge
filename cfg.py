import json
import os
from datetime import date


# для сортировки Thumb в сетке
# имя каждого ключа соответствует аттрибуту Thumb

ORDER: dict[str, dict] = {
        "name": {"text": "Имя", "index": 0},
        "size": {"text": "Размер", "index": 1},
        "mod": {"text": "Дата", "index": 2},
        "type": {"text": "Тип", "index": 3},
        "colors": {"text": "Цвета", "index": 4},
        "rating": {"text": "Рейтинг", "index": 5},
        }

# это базовое значение Pixmap которые улетают в базу данных
IMG_SIZE: int = 210

# ширина Pixmap в Thumb
PIXMAP_SIZE: list = [90, 130, 170, IMG_SIZE]

# ширина целого Thumb исходя из PIXMAP_SIZE
THUMB_WIDTH: list = [130, 150, 170, IMG_SIZE]

# ширина текста Thumb исходя из PIXMAP_SIZE
TEXT_LENGTH: list = [15, 18, 23, 28]

# высота целого Thumb исхозя из выбранного индекса в настройках (view_rows)
THUMB_HEIGHT: list = [174, 198, 230]

# расстояние в сетке
GRID_SPACING = 1

class JsonData:
    root = "/Volumes"
    ww = 1050
    hh = 700
    ww_im = 700
    hh_im = 500
    sort = list(ORDER.keys())[0]
    reversed = False
    extra_paths = ["/Studio/PANACEA", "/Studio/MIUZ"]
    favs = {}
    list_view = False
    clear_db = 5
    tab_bar = 1
    thumb_size = PIXMAP_SIZE[0]
    view_rows = 2

    @classmethod
    def get_data(cls):
        return [
            i for i in dir(cls)
            if not i.startswith("__")
            and
            not callable(getattr(cls, i))
            ]


class Config:
    APP_NAME = "PseudoBridge"
    APP_VER = "1.0.0"

    JSON_FILE = os.path.join(os.path.expanduser('~'), 'Desktop', 'cfg.json')
    DB_FILE = os.path.join(os.path.expanduser('~'), 'Desktop', 'db.db')

    IMG_EXT: tuple = (
        ".jpg", "jpeg", "jfif",
        ".tif", ".tiff",
        ".psd", ".psb",
        ".png",
        ".nef", ".cr2", ".cr3", ".arw", ".raf"
        )
      
    COLORS: dict = {
        "\U0001F534": "Красный",
        "\U0001F535": "Синий",
        "\U0001F7E0": "Оранжевый",
        "\U0001F7E1": "Желтый",
        "\U0001F7E2": "Зеленый",
        "\U0001F7E3": "Фиолетовый",
        "\U0001F7E4": "Коричневый"
        }

    color_filters: list = []
    rating_filter: int = 0
    image_apps: dict = {}

    @classmethod
    def read_json_data(cls) -> dict:

        if os.path.exists(cls.JSON_FILE):

            with open(cls.JSON_FILE, 'r') as f:

                try:
                    json_data: dict = json.load(f)
                
                    for k, v in json_data.items():
                        if hasattr(JsonData, k):
                            setattr(JsonData, k, v)

                except json.JSONDecodeError:
                    print("Ошибка чтения json")
                    cls.write_config()

        else:
            print("файла не существует")
            cls.write_config()

    @classmethod
    def write_config(cls):
        # мы пишем тут данные из JsonData, независимо от успешности чтения
        # cfg.json

        new_data: dict = {
            attr: getattr(JsonData, attr)
            for attr in JsonData.get_data()
            }

        try:
            with open(cls.JSON_FILE, 'w') as f:
                json.dump(new_data, f, indent=4, ensure_ascii=False)
            return True
        
        except Exception as e:
            print(e)
            return False

    @classmethod
    def find_img_apps(cls):
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
        cls.image_apps["Просмотр"] = "/System/Applications/Preview.app"

        for item in os.listdir(root_path):
            full_path = os.path.join(root_path, item)
            app_folder = any(x for x in names if item in x)
            app_app = any(x for x in names_app if item in x)

            if app_folder:        
                app_inside_folder = os.path.join(full_path, item + ".app")
                if os.path.exists(app_inside_folder):
                    cls.image_apps[item] = app_inside_folder

            elif app_app:
                item = item.replace(".app", "")
                cls.image_apps[item] = full_path


Config.read_json_data()
Config.find_img_apps()
