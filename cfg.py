import json
import os
import subprocess
from datetime import date

HEX = "85d3b3a7ed89b1d7bd6e94524005ca81"
HEX_DEFAULT = "ZERO"

class Static:
    APP_NAME = "PreudoBridge"
    APP_VER = 1.7

    APP_SUPPORT = os.path.expanduser('~/Library/Application Support')
    ROOT = os.path.join(APP_SUPPORT, APP_NAME)

    JSON_FILE = os.path.join(ROOT, 'cfg.json')
    DB_FILENAME = ".preudobridge.db"

    USER_APPS = "/Applications"

    GRAY_SLIDER = "rgba(111, 111, 111, 0.5)"
    GRAY_UP_BTN = "rgba(128, 128, 128, 0.40)"
    BLUE = "rgb(46, 89, 203)"

    ARROW_RIGHT = " \U0000203A" # ›
    STAR_SYM = "\U00002605" # ★
    UP_ARROW_SYM = "\u25B2" # ▲
    LINE_SYM = "\U00002014" # —
    PARAGRAPH_SEP = "\u2029"
    LINE_FEED  = "\u000a"

    DEINED_SYM = "⚠"
    # DEINED_SYM = "🔴"
    REVIEW_SYM = "◌"
    # REVIEW_SYM = "🟡"
    APPROVED_SYM = "✓"
    # APPROVED_SYM = "🟢"

    NO_TAGS_T = "Без меток"
    DEINED_T = "Отклонено"
    REVIEW_T = "Модерация"
    APPROVED_T = "Принято"

    SCRIPTS_DIR = "scripts"
    REVEAL_SCPT = os.path.join(SCRIPTS_DIR, "reveal_files.scpt")

    IMAGES_DIR = "images"
    IMG_SVG = os.path.join(IMAGES_DIR, "img.svg")
    FILE_SVG = os.path.join(IMAGES_DIR, "file.svg")
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
    CLEAR_SVG = os.path.join(IMAGES_DIR, "clear.svg")
    HIDE_SVG = os.path.join(IMAGES_DIR, "hide.svg")
    SHOW_SVG = os.path.join(IMAGES_DIR, "show.svg")

    FOLDER_UP_SVG = os.path.join(IMAGES_DIR, "folder_up.svg")
    GRID_VIEW_SVG = os.path.join(IMAGES_DIR, "grid_view.svg")
    LIST_VIEW_SVG = os.path.join(IMAGES_DIR, "list_view.svg")
    NAVIGATE_BACK_SVG = os.path.join(IMAGES_DIR, "navigate_back.svg")
    NAVIGATE_NEXT_SVG = os.path.join(IMAGES_DIR, "navigate_next.svg")
    RATING_SVG = os.path.join(IMAGES_DIR, "rating.svg")
    SETTINGS_SVG = os.path.join(IMAGES_DIR, "settings.svg")

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

    FAVORITES_NAME = "___favs___"
    MAIN_WIN_NAME = "MainWin"

    SEARCH_TEMPLATES = {
        "Найти jpg": (".jpg", ".jpeg", "jfif"),
        "Найти png": (".png"),
        "Найти tiff": (".tif", ".tiff"),
        "Найти psd/psb": (".psd", ".psb"),
        "Найти raw": (".nef", ".raw"),
        "Найти любые фото": IMG_EXT
    }

    SEARCH_LIST_TEXT = "Найти по списку"
    SEARCH_LIST = []


class ThumbData:

    # кешированные изображения загружаются для отобажения в сетке виджетов
    DB_PIXMAP_SIZE: int = 210

    # ширина и высота Thumbnail
    THUMB_H = [120, 140, 175, 260]
    THUMB_W = [140, 140, 180, 230]


    # шаг 20 пикселей
    # максимальный размер в пикселях по широкой стороне для изображения
    PIXMAP_SIZE: list = [50, 70, 100, 170]

    # шаг 7 пунктов
    # текстовый виджет и цветовые метки не имеют ширины, но ширина ограничена
    # количеством символов в тексте данных виджетов
    MAX_ROW: list = [20, 20, 25, 32]

    # растояние между изображением, текстовым и цветовым виджетами
    SPACING = 2

    # дополнительное пространство вокруг Pixmap
    OFFSET = 15


class JsonData:
    hex = HEX_DEFAULT
    root = f"/Volumes"
    extra_paths = ["/Studio/PANACEA", "/Studio/MIUZ"]
    favs = {}

    udpdate_file_paths = [
        '/Volumes/Shares/Studio/MIUZ/Photo/Art/Raw/2024/soft/PreudoBridge.zip',
        '/Volumes/Shares-1/Studio/MIUZ/Photo/Art/Raw/2024/soft/PreudoBridge.zip',
        '/Volumes/Shares-2/Studio/MIUZ/Photo/Art/Raw/2024/soft/PreudoBridge.zip',
        '/Volumes/Shares-3/Studio/MIUZ/Photo/Art/Raw/2024/soft/PreudoBridge.zip',
        ]

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
    def ver_check(cls):
        if cls.hex == HEX_DEFAULT or cls.hex != HEX:
            
            # удаляем все кроме json за ненужностью

            for i in os.scandir(Static.ROOT):
                if i.path != Static.JSON_FILE:
                    subprocess.call(["rm", "-rf", i.path])

            cls.hex = HEX

    @classmethod
    def init(cls):
        os.makedirs(Static.ROOT, exist_ok=True)
        cls.read_json_data()
        cls.ver_check()
        cls.write_config()
        cls.find_img_apps()


class Dynamic:
    rating_filter: int = 0
    grid_view_type: int = 0
    ww = 1050
    hh = 700
    ww_im = 700
    hh_im = 500
    left_menu_tab = 1
    pixmap_size_ind = 0
    rev: bool = False
    sort: str = "name"
    busy_db: bool = False