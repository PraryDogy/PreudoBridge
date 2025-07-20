import json
import os
import shutil
import re

class Static:
    APP_NAME = "PreudoBridge"
    APP_VER = 2.35

    USER_SETTINGS_DIR = os.path.expanduser('~/Library/Application Support')
    APP_SUPPORT_APP = os.path.join(USER_SETTINGS_DIR, APP_NAME)

    GENERIC_ICONS_DIR = os.path.join(APP_SUPPORT_APP, "icons")
    JSON_FILE = os.path.join(APP_SUPPORT_APP, 'cfg.json')

    USER_APPS_DIR = "/Applications"

    SCRIPTS_DIR = "scripts"
    REVEAL_SCPT = os.path.join(SCRIPTS_DIR, "reveal_files.scpt")
    REMOVE_FILES_SCPT = os.path.join(SCRIPTS_DIR, "remove_files.scpt")

    IMAGES_DIR = "images"
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
    SETTINGS_SVG = os.path.join(IMAGES_DIR, "settings.svg")
    COPY_FILES_SVG = os.path.join(IMAGES_DIR, "copy_files.svg")
    COPY_FILES_PNG = os.path.join(IMAGES_DIR, "copy_files.svg")
    WARNING_SVG = os.path.join(IMAGES_DIR, "warning.svg")
    NEW_WIN_SVG = os.path.join(IMAGES_DIR, "new_win.svg")
    QUESTION_SVG = os.path.join(IMAGES_DIR, "question.svg")
    CASCADE_SVG = os.path.join(IMAGES_DIR, "cascade.svg")
    SYSTEM_THEME_SVG = os.path.join(IMAGES_DIR, "system_theme.svg")
    DARK_THEME_SVG = os.path.join(IMAGES_DIR, "dark_theme.svg")
    LIGHT_THEME_SVG = os.path.join(IMAGES_DIR, "light_theme.svg")
    FAST_SORT_SVG = os.path.join(IMAGES_DIR, "fast_sort.svg")

    DB_FILENAME = ".preudobridge.db"
    FOLDER_TYPE: str = "folder"
    VOLUMES: str = "Volumes"
    USERS: str = "Users"
    SVG = "SVG"

    GRAY_GLOBAL = "rgba(128, 128, 128, 0.95)"
    BLUE_GLOBAL = "rgb(46, 89, 203)"

    STAR_SYM = "\U00002605" # ★
    LINE_LONG_SYM = "\U00002014" # —
    PARAGRAPH_SEP = "\u2029" # символ PyQt5, который равен новой строке
    LINE_FEED  = "\u000a" # символ PyQt5, который равен новой строке

    ext_jpeg = (
        ".jpg", ".JPG",
        ".jpeg", ".JPEG",
        ".jpe", ".JPE",
        ".jfif", ".JFIF",
        ".bmp", ".BMP",
        ".dib", ".DIB",
        ".webp", ".WEBP",
        ".ppm", ".PPM",
        ".pgm", ".PGM",
        ".pbm", ".PBM",
        ".pnm", ".PNM",
        ".gif", ".GIF",
        ".ico", ".ICO",
    )

    ext_tiff = (
        ".tif", ".TIF",
        ".tiff", ".TIFF",
    )

    ext_psd = (
        ".psd", ".PSD",
        ".psb", ".PSB",
    )

    ext_png = (
        ".png", ".PNG",
    )

    ext_raw = (
        ".nef", ".NEF",
        ".cr2", ".CR2",
        ".cr3", ".CR3",
        ".arw", ".ARW",
        ".raf", ".RAF",
        ".dng", ".DNG",
        ".rw2", ".RW2",
        ".orf", ".ORF",
        ".srw", ".SRW",
        ".pef", ".PEF",
        ".rwl", ".RWL",
        ".mos", ".MOS",
        ".kdc", ".KDC",
        ".mrw", ".MRW",
        ".x3f", ".X3F",
    )

    ext_video = (
        ".avi", ".AVI",
        ".mp4", ".MP4",
        ".mov", ".MOV",
        ".mkv", ".MKV",
        ".wmv", ".WMV",
        ".flv", ".FLV",
        ".webm", ".WEBM",
    )

    ext_all = (
        *ext_jpeg,
        *ext_tiff,
        *ext_psd,
        *ext_png,
        *ext_raw,
        *ext_video,
    )

    hidden_file_syms: tuple[str] = (".", "~$", "$")
    theme_macintosh = "macintosh"
    theme_fusion = "Fusion"


class ThumbData:

    # размер в пикселях по длинной стороне изображения для базы данных
    DB_IMAGE_SIZE: int = 210

    # ширина и высота grid.py > Thumb
    THUMB_H = [130, 150, 185, 270]
    THUMB_W = [140, 140, 180, 230]

    # максимальный размер изображения в пикселях для grid.py > Thumb
    PIXMAP_SIZE: list = [50, 70, 100, 170]

    # максимальное количество символов на строку для grid.py > Thumb
    MAX_ROW: list = [20, 20, 25, 32]

    CORNER: list = [4, 8, 14, 16]

    # растояние между изображением и текстом для grid.py > Thumb
    SPACING = 2

    # дополнительное пространство вокруг изображения для grid.py > Thumb
    OFFSET = 15


class JsonData:
    favs = {}
    show_hidden = False
    go_to_now = False
    dark_mode = None    
    generic_icons_removed = False
    app_names = [
        "preview",
        "photos",
        "photoshop",
        "lightroom",
        "affinity photo",
        "pixelmator",
        "gimp",
        "capture one",
        "dxo photolab",
        "luminar neo",
        "sketch",
        "graphicconverter",
        "imageoptim",
        "snapheal",
        "photoscape",
        "preview",
        "просмотр"
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
            print("файла cfg.json не существует")
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
                Dynamic.generic_icon_paths.append(entry.path)

        from system.utils import Utils
        path = Utils.get_generic_icon_path(Static.FOLDER_TYPE, Static.GENERIC_ICONS_DIR)
        shutil.copyfile(Static.FOLDER_SVG, path)
        Dynamic.generic_icon_paths.append(path)

    @classmethod
    def do_before_start(cls):
        if not os.path.exists(Static.GENERIC_ICONS_DIR):
            return
        if JsonData.generic_icons_removed == False:
            pattern = re.compile(r'^_[^/\\]+\.svg$')

            for entry in os.scandir(Static.GENERIC_ICONS_DIR):
                if not pattern.fullmatch(entry.name):
                    os.remove(entry.path)
                    print(f"Removed: {entry.name}")

            JsonData.generic_icons_removed = True

    @classmethod
    def init(cls):
        os.makedirs(Static.APP_SUPPORT_APP, exist_ok=True)
        cls.read_json_data()
        cls.write_config()
        try:
            cls.do_before_start()
        except Exception as e:
            print("do before start", e)

        cls.setup_generic_icons()

class Dynamic:
    rating_filter: int = 0
    pixmap_size_ind = 0
    generic_icon_paths: list[str] = []
    urls_to_copy: list[str] = []
    reading = False
    image_apps: dict[str, str] = {}