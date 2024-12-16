import json
import os
from datetime import date


class Static:
    APP_NAME = "PreudoBridge"
    APP_VER = 1.2

    APP_SUPPORT = os.path.expanduser('~/Library/Application Support')
    ROOT = os.path.join(APP_SUPPORT, APP_NAME)

    HASH_DIR = os.path.join(ROOT, "hashdir")
    JSON_FILE = os.path.join(ROOT, 'cfg.json')
    DB_FILE = os.path.join(ROOT, 'db.db')

    USER_APPS = "/Applications"

    GRAY_SLIDER = "rgba(111, 111, 111, 0.5)"
    GRAY_UP_BTN = "rgba(128, 128, 128, 0.40)"
    BLUE = "rgb(46, 89, 203)"

    STAR_SYM = "\U00002605"
    GRID_SYM = "\U00001392"
    BURGER_SYM = "\U00002630"
    FAT_DOT_SYM = "\U000026AB"
    FILTERS_CROSS_SYM = "\u2715" 
    SEARCH_CROSS_SYM = "\u2573"
    UP_ARROW_SYM = "\u25B2"
    BACK_SYM = "\u276E"
    NEXT_SYM = "\u276F"
    UP_CURVE = "\u2934" 
    SETT_SYM = "\U00002699"

    PARAGRAPH_SEP = "\u2029"
    LINE_FEED  = "\u000a"

    IMAGES_DIR = "images"
    IMG_SVG = os.path.join(IMAGES_DIR, "img.svg")
    FOLDER_SVG = os.path.join(IMAGES_DIR, "folder.svg")
    HDD_SVG = os.path.join(IMAGES_DIR, "hdd.svg")
    COMP_SVG = os.path.join(IMAGES_DIR, "computer.svg")
    GOTO_SVG = os.path.join(IMAGES_DIR, "goto.svg")
    ZOOM_OUT_SVG = os.path.join(IMAGES_DIR, "zoom_out.svg")
    ZOOM_IN_SVG = os.path.join(IMAGES_DIR, "zoom_in.svg")
    ZOOM_FIT_SVG = os.path.join(IMAGES_DIR, "zoom_fit.svg")
    CLOSE_SVG = os.path.join(IMAGES_DIR, "zoom_close.svg")
    PREV_SVG = os.path.join(IMAGES_DIR, "prev.svg")
    NEXT_SVG = os.path.join(IMAGES_DIR, "next.svg")
    ICON_SVG = os.path.join(IMAGES_DIR, "icon.svg")

    FOLDER_TYPE: str = "Папка"

    GRID_SPACING = 5
    LEFT_MENU_W = 240

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

    FAVORITES_NAME = "___favs___"
    MAIN_WIN_NAME = "MainWin"


class ThumbData:

    # максимальный размер в пикселях по широкой стороне для кешируемого
    # изображения в папку "hashdir" в AppliactionSupport
    # кешированные изображения загружаются для отобажения в сетке виджетов
    DB_PIXMAP_SIZE: int = 210

    # ширина и высота Thumbnail
    THUMB_H = [110, 130, 160, 180, 250]
    THUMB_W = [140, 140, 170, 180, 220]


    # шаг 20 пикселей
    # максимальный размер в пикселях по широкой стороне для изображения
    PIXMAP_SIZE: list = [50, 70, 100, 120, 170]

    # шаг 7 пунктов
    # текстовый виджет и цветовые метки не имеют ширины, но ширина ограничена
    # количеством символов в тексте данных виджетов
    MAX_ROW: list = [20, 20, 25, 28, 32]

    # виджет с цветовыми метками имеет только 1 строку высотой 16 пикселей
    COLOR_WID_H = 16

    # растояние между изображением, текстовым и цветовым виджетами
    SPACING = 2

    # дополнительное пространство вокруг Pixmap
    OFFSET = 6


class JsonData:
    root = f"/Volumes"

    # database > CACHE > column name = "name"
    # базовая сортировка по имени по возрастанию
    sort = "name"

    reversed = False
    extra_paths = ["/Studio/PANACEA", "/Studio/MIUZ"]
    favs = {}

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

        if os.path.exists(Static.JSON_FILE):

            with open(Static.JSON_FILE, 'r', encoding="utf-8") as f:

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
            with open(Static.JSON_FILE, 'w', encoding="utf-8") as f:
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
        Static.IMAGE_APPS["Просмотр"] = f"/System/Applications/Preview.app"

        with os.scandir(Static.USER_APPS) as entries:
            for entry in entries:
                if not entry.is_dir():
                    continue

                # Проверяем, если имя соответствует папке
                app_folder = any(entry.name == name for name in names)
                if app_folder:
                    app_inside_folder = os.path.join(entry.path, entry.name + ".app")
                    if os.path.exists(app_inside_folder):
                        Static.IMAGE_APPS[entry.name] = app_inside_folder
                    continue

                # Проверяем, если имя соответствует .app
                app_app = any(entry.name == name_app for name_app in names_app)
                if app_app:
                    item = entry.name.replace(".app", "")
                    Static.IMAGE_APPS[item] = entry.path

    @classmethod
    def init(cls):
        os.makedirs(Static.ROOT, exist_ok=True)
        cls.read_json_data()
        cls.find_img_apps()


class Dynamic:
    color_filters: list = []
    rating_filter: int = 0
    grid_view_type: int = 0
    ww = 1050
    hh = 700
    ww_im = 700
    hh_im = 500
    left_menu_tab = 1
    pixmap_size_ind = 0