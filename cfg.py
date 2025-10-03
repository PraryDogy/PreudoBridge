import json
import os
import re
import shutil
from collections import defaultdict


class Static:
    APP_NAME = "PreudoBridge"
    APP_VER = 3.12

    APP_SUPPORT = os.path.join(os.path.expanduser('~/Library/Application Support'), APP_NAME)
    EXTERNAL_ICONS = os.path.join(APP_SUPPORT, "icons")
    JSON_FILE = os.path.join(APP_SUPPORT, 'cfg.json')
    DB_FILE = os.path.join(APP_SUPPORT, 'db.db')
    THUMBNAILS = os.path.join(APP_SUPPORT, 'thumbnails')

    APPLE_SCRIPTS = {entry.name: entry.path for entry in os.scandir("scripts")}
    INTERNAL_ICONS = {entry.name: entry.path for entry in os.scandir("icons")}

    FOLDER_TYPE: str = "folder"
    VOLUMES: str = "Volumes"

    GRAY_GLOBAL = "rgba(128, 128, 128, 0.95)"
    BLUE_GLOBAL = "rgb(70, 130, 240)"

    STAR_SYM = "\U00002605" # ★
    LINE_LONG_SYM = "\U00002014" # —
    PARAGRAPH_SEP = "\u2029" # символ PyQt5, который равен новой строке
    LINE_FEED  = "\u000a" # символ PyQt5, который равен новой строке

    hidden_file_syms: tuple[str] = (".", "~$", "$")

    ext_app = (".app", ".APP")

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

    excel_ext = [".xls", ".xlsx", ".xlsm", ".xlt", ".xltx", ".xltm", ".xlsb", ".xlw"]
    word_ext  = [".doc", ".docx", ".dot", ".dotx", ".docm", ".dotm"]
    ppt_ext   = [".ppt", ".pptx", ".pptm", ".pot", ".potx", ".potm", ".pps", ".ppsx", ".ppsm"]
    pdf_ext   = [".pdf"]
    archive_ext = [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso", ".cab", ".tgz", ".z"]
    db_ext    = [".db", ".sqlite", ".sqlite3", ".mdb", ".accdb"]
    audio_ext = [".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a", ".wma"]
    ai_ext = [".ai"]
    indd_ext = [".indd"]
    # app, dmg, pkg

    PRELOADED_ICONS = {
        **{ext: "icons/excel.svg"   for ext in excel_ext},
        **{ext: "icons/word.svg"    for ext in word_ext},
        **{ext: "icons/ppt.svg"     for ext in ppt_ext},
        **{ext: "icons/pdf.svg"     for ext in pdf_ext},
        **{ext: "icons/archive.svg" for ext in archive_ext},
        **{ext: "icons/audio.svg"   for ext in audio_ext},
        **{ext: "icons/ai.svg"      for ext in ai_ext},
        **{ext: "icons/indd.svg"    for ext in indd_ext},
        **{ext: "icons/db.svg"      for ext in db_ext},
    }

    DATA_LIMITS = {
        0: {"bytes": 200 * 1024 * 1024, "text": "200 МБ"},
        1: {"bytes": 500 * 1024 * 1024, "text": "500 МБ"},
        2: {"bytes": 1000 * 1024 * 1024, "text": "1 ГБ"},
        3: {"bytes": 2000 * 1024 * 1024, "text": "2 ГБ"},
        4: {"bytes": 5000 * 1024 * 1024, "text": "5 ГБ"},
        5: {"bytes": 10000 * 1024 * 1024, "text": "10 ГБ"},
    }

class ThumbData:

    # размер в пикселях по длинной стороне изображения для базы данных
    DB_IMAGE_SIZE: int = 210

    # ширина и высота grid.py > Thumb
    THUMB_H = [130, 150, 185, 270]
    THUMB_W = [145, 145, 180, 230]

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
    show_text = False
    data_limit = len(Static.DATA_LIMITS) -1
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
    def setup_icons(cls):
        os.makedirs(Static.EXTERNAL_ICONS, exist_ok=True)

    @classmethod
    def do_before_start(cls):
        ...

    @classmethod
    def init(cls):
        os.makedirs(Static.APP_SUPPORT, exist_ok=True)
        cls.read_json_data()
        cls.write_config()
        try:
            cls.do_before_start()
        except Exception as e:
            print("do before start", e)

        cls.setup_icons()

class Dynamic:
    rating_filter: int = 0
    pixmap_size_ind = 0
    image_apps: dict[str, str] = {}
