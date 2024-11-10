import json
import os
from datetime import date

APP_NAME = "PreudoBridge"
APP_VER = "1.0.0"

# ROOT = os.path.expanduser("~/Desktop")

APP_SUPPORT = os.path.expanduser('~/Library/Application Support')
ROOT = os.path.join(APP_SUPPORT, APP_NAME)

HASH_DIR = os.path.join(ROOT, "hashdir")
JSON_FILE = os.path.join(ROOT, 'cfg.json')
DB_FILE = os.path.join(ROOT, 'db.db')

USER_APPS = "/Applications"

GRAY = "rgba(111, 111, 111, 0.5)"
BLUE = "rgba(0, 122, 255, 1)"

STAR_SYM = "\U00002605"
GRID_SYM = "\U00001392"
BURGER_SYM = "\U00002630"
FAT_DOT_SYM = "\U000026AB"
FILTERS_CROSS_SYM = "\u2715" 
SEARCH_CROSS_SYM = "\u2573"
UP_ARROW_SYM = "\u25B2"
BACK_SYM = "\u25C0"
NEXT_SYM = "\u25B6"
UP_CURVE = "\u2934" 

FOLDER: str = "Папка"

MARGIN: dict = {"w": 50, "h": 10}
MAX_SIZE: int = 210
PIXMAP_SIZE: list = [50, 95, 130, 170, MAX_SIZE]
THUMB_W: list = [i for i in PIXMAP_SIZE]
TEXT_LENGTH: list = [12, 18, 23, 28, 33]
GRID_SPACING = 5
LEFT_MENU_W = 240
MAX_VAR = len(PIXMAP_SIZE) - 1

LINK = "https://disk.yandex.ru/d/vYdK8hMwVbkSKQ"
IMAGE_APPS: dict = {}

_IMG_EXT: tuple = (
    ".jpg", ".jpeg", ".jfif",
    ".tif", ".tiff",
    ".psd", ".psb",
    ".png",
    ".nef", ".cr2", ".cr3", ".arw", ".raf"
    )
IMG_EXT: tuple = tuple(
    upper_ext
    for ext in _IMG_EXT
    for upper_ext in (ext, ext.upper())
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


class JsonData:
    root = f"/Volumes"
    ww = 1050
    hh = 700
    ww_im = 700
    hh_im = 500
    sort = "name" # database > CACHE > column "name"
    reversed = False
    extra_paths = ["/Studio/PANACEA", "/Studio/MIUZ"]
    favs = {}
    list_view = False
    tab_bar = 1
    pixmap_size_ind = 0

    @classmethod
    def get_data(cls):
        return [
            i for i in dir(cls)
            if not i.startswith("__")
            and
            not callable(getattr(cls, i))
            ]

    @classmethod
    def read_json_data(cls) -> dict:

        if os.path.exists(JSON_FILE):

            with open(JSON_FILE, 'r', encoding="utf-8") as f:

                try:
                    json_data: dict = json.load(f)
                
                    for k, v in json_data.items():
                        if hasattr(cls, k):
                            setattr(cls, k, v)

                except json.JSONDecodeError:
                    print("Ошибка чтения json")
                    cls.write_config()

        else:
            print("файла не существует")
            cls.write_config()

    @classmethod
    def write_config(cls):
        new_data: dict = {
            attr: getattr(cls, attr)
            for attr in cls.get_data()
            }

        try:
            with open(JSON_FILE, 'w', encoding="utf-8") as f:
                json.dump(new_data, f, indent=4, ensure_ascii=False)
            return True
        
        except Exception as e:
            print(e)
            return False

    @classmethod
    def find_img_apps(cls):
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
        IMAGE_APPS["Просмотр"] = f"/System/Applications/Preview.app"

        for item in os.listdir(USER_APPS):
            full_path = os.path.join(USER_APPS, item)
            app_folder = any(x for x in names if item in x)
            app_app = any(x for x in names_app if item in x)

            if app_folder:        
                app_inside_folder = os.path.join(full_path, item + ".app")
                if os.path.exists(app_inside_folder):
                    IMAGE_APPS[item] = app_inside_folder

            elif app_app:
                item = item.replace(".app", "")
                IMAGE_APPS[item] = full_path

    @classmethod
    def init(cls):
        os.makedirs(ROOT, exist_ok=True)
        cls.read_json_data()
        cls.find_img_apps()

class Dymanic:
    color_filters: list = []
    rating_filter: int = 0
