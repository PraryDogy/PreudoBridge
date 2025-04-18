import json
import os
import shutil


class Static:
    APP_NAME = "PreudoBridge"
    APP_VER = 2.05

    USER_SETTINGS_DIR = os.path.expanduser('~/Library/Application Support')
    APP_SUPPORT_APP = os.path.join(USER_SETTINGS_DIR, APP_NAME)
    GENERIC_ICONS_DIR = os.path.join(APP_SUPPORT_APP, "icons")
    SCRIPTS_DIR = "scripts"
    JSON_FILE = os.path.join(APP_SUPPORT_APP, 'cfg.json')
    USER_APPS_DIR = "/Applications"

    REVEAL_SCPT = os.path.join(SCRIPTS_DIR, "reveal_files.scpt")
    REMOVE_FILES_SCPT = os.path.join(SCRIPTS_DIR, "remove_files.scpt")

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
    GENERIC_SVG = os.path.join(IMAGES_DIR, "generic.svg")
    FOLDER_UP_SVG = os.path.join(IMAGES_DIR, "folder_up.svg")
    GRID_VIEW_SVG = os.path.join(IMAGES_DIR, "grid_view.svg")
    LIST_VIEW_SVG = os.path.join(IMAGES_DIR, "list_view.svg")
    NAVIGATE_BACK_SVG = os.path.join(IMAGES_DIR, "navigate_back.svg")
    NAVIGATE_NEXT_SVG = os.path.join(IMAGES_DIR, "navigate_next.svg")
    SETTINGS_SVG = os.path.join(IMAGES_DIR, "settings.svg")
    COPY_FILES_SVG = os.path.join(IMAGES_DIR, "copy_files.svg")
    COPY_FILES_PNG = os.path.join(IMAGES_DIR, "copy_files.svg")
    WARNING_SVG = os.path.join(IMAGES_DIR, "warning.svg")
    NEW_WIN_SVG = os.path.join(IMAGES_DIR, "new_win.svg")

    DB_FILENAME = ".preudobridge.db"
    FOLDER_TYPE: str = "folder"
    VOLUMES: str = "Volumes"
    USERS: str = "Users"
    SVG = "SVG"

    GRAY_GLOBAL = "rgba(128, 128, 128, 0.40)"
    BLUE_GLOBAL = "rgb(46, 89, 203)"

    STAR_SYM = "\U00002605" # ★
    LINE_LONG_SYM = "\U00002014" # —
    PARAGRAPH_SEP = "\u2029" # символ PyQt5, который равен новой строке
    LINE_FEED  = "\u000a" # символ PyQt5, который равен новой строке

    DEINED_SYM = "⚠"
    REVIEW_SYM = "◌"
    APPROVED_SYM = "✓"

    TAGS_NO_TAGS = "Без меток"
    TAGS_DEINED = "Отклонено"
    TAGS_REVIEW = "Модерация"
    TAGS_APPROWED = "Принято"

    LEFT_MENU_W = 240

    LINK = "https://disk.yandex.ru/d/vYdK8hMwVbkSKQ"

    IMG_EXT: tuple = (
        ".jpg", ".jpeg", ".jfif",
        ".tif", ".tiff",
        ".psd", ".psb",
        ".png",
        ".nef", ".cr2", ".cr3", ".arw", ".raf",
        ".mov", ".mp4",
        ".JPG", ".JPEG", ".JFIF",
        ".TIF", ".TIFF",
        ".PSD", ".PSB",
        ".PNG",
        ".NEF", ".CR2", ".CR3", ".ARW", ".RAF",
        ".MOV", ".MP4"
    )

    SEARCH_EXTENSIONS = {
        "Найти jpg": (".jpg", ".jpeg", "jfif"),
        "Найти png": (".png"),
        "Найти tiff": (".tif", ".tiff"),
        "Найти psd/psb": (".psd", ".psb"),
        "Найти raw": (".nef", ".raw"),
        "Найти любые фото": IMG_EXT
    }

    SEARCH_LIST_TEXT = "Найти по списку"


class ThumbData:

    # размер в пикселях по длинной стороне изображения для базы данных
    DB_IMAGE_SIZE: int = 210

    # ширина и высота grid.py > Thumb
    THUMB_H = [120, 140, 175, 260]
    THUMB_W = [140, 140, 180, 230]

    # максимальный размер изображения в пикселях для grid.py > Thumb
    PIXMAP_SIZE: list = [50, 70, 100, 170]

    # максимальное количество символов на строку для grid.py > Thumb
    MAX_ROW: list = [20, 20, 25, 32]

    # растояние между изображением и текстом для grid.py > Thumb
    SPACING = 2

    # дополнительное пространство вокруг изображения для grid.py > Thumb
    OFFSET = 15


class JsonData:
    favs = {}

    udpdate_file_paths = [
        '/Volumes/Shares/Studio/MIUZ/Photo/Art/Raw/2024/soft/PreudoBridge.zip',
        '/Volumes/Shares-1/Studio/MIUZ/Photo/Art/Raw/2024/soft/PreudoBridge.zip',
        '/Volumes/Shares-2/Studio/MIUZ/Photo/Art/Raw/2024/soft/PreudoBridge.zip',
        '/Volumes/Shares-3/Studio/MIUZ/Photo/Art/Raw/2024/soft/PreudoBridge.zip',
        ]
    
    generic_icons_removed = False

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
    def setup_generic_icons(cls):
        os.makedirs(Static.GENERIC_ICONS_DIR, exist_ok=True)
        for entry in os.scandir(Static.GENERIC_ICONS_DIR):
            if entry.name.endswith(".svg"):
                Dynamic.GENERIC_ICON_PATHS.append(entry.path)

        from utils import Utils
        path = Utils.get_generic_icon_path(Static.FOLDER_TYPE)

        if not os.path.exists(path):
            shutil.copyfile(Static.FOLDER_SVG, path)

        elif os.path.getsize(Static.FOLDER_SVG) != os.path.getsize(path):
            shutil.copyfile(Static.FOLDER_SVG, path)

        Dynamic.GENERIC_ICON_PATHS.append(path)

    @classmethod
    def do_before_start(cls):
        if JsonData.generic_icons_removed == False:
            for entry in os.scandir(Static.GENERIC_ICONS_DIR):
                if not entry.name.startswith(Static.SVG + "_"):
                    os.remove(entry.path)
            JsonData.generic_icons_removed = True

    @classmethod
    def init(cls):
        os.makedirs(Static.APP_SUPPORT_APP, exist_ok=True)
        cls.read_json_data()
        cls.write_config()
        cls.setup_generic_icons()

        try:
            cls.do_before_start()
        except Exception as e:
            print("do before start", e)

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
    files_to_copy: list[str] = []
    EXACT_SEARCH = False
    SEARCH_LIST = []

    # [path_to_svg_icon, ...] в GENERIC_ICONS
    GENERIC_ICON_PATHS: list[str] = []
