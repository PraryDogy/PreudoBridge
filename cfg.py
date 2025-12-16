import json
import os
import shutil


class Static:
    app_name = "PreudoBridge"
    app_ver = 3.70

    app_support = os.path.join(os.path.expanduser('~/Library/Application Support'), app_name)
    uti_icons = os.path.join(app_support, "uti_icons")
    thumbnails_dir = os.path.join(app_support, 'thumbnails')
    cfg_file = os.path.join(app_support, 'cfg.json')
    db_file = os.path.join(app_support, 'db.db')

    scripts_rel_dir = "./scripts"
    icons_rel_dir = "./icons"

    folder_type = "folder"
    rgba_gray = "rgba(128, 128, 128, 0.95)"
    rgba_blue = "rgb(70, 130, 240)"
    star_symbol = "\U00002605" # ★
    long_line_symbol = "\U00002014" # —
    paragraph_symbol = "\u2029" # символ PyQt5, который равен новой строке
    line_feed_symbol  = "\u000a" # символ PyQt5, который равен новой строке
    hidden_symbols = (".", "~$", "$")

    base_ww, base_hh = 1120, 760

    app_exts = (".app", ".APP")

    jpg_exts = (
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

    tiff_exts = (
        ".tif", ".TIF",
        ".tiff", ".TIFF",
    )

    psd_exts = (
        ".psd", ".PSD",
        ".psb", ".PSB",
    )

    png_exts = (
        ".png", ".PNG",
    )

    raw_exts = (
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

    movie_exts = (
        ".avi", ".AVI",
        ".mp4", ".MP4",
        ".mov", ".MOV",
        ".mkv", ".MKV",
        ".wmv", ".WMV",
        ".flv", ".FLV",
        ".webm", ".WEBM",
    )

    icns_exts = (
        ".icns", ".ICNS",
    )

    img_exts = (
        *jpg_exts,
        *tiff_exts,
        *psd_exts,
        *png_exts,
        *raw_exts,
        *movie_exts,
        *icns_exts,
    )

    limit_mappings = {
        0: {"bytes": 200 * 1024 * 1024, "text": "200 МБ"},
        1: {"bytes": 500 * 1024 * 1024, "text": "500 МБ"},
        2: {"bytes": 1000 * 1024 * 1024, "text": "1 ГБ"},
        3: {"bytes": 2000 * 1024 * 1024, "text": "2 ГБ"},
        4: {"bytes": 5000 * 1024 * 1024, "text": "5 ГБ"},
        5: {"bytes": 10000 * 1024 * 1024, "text": "10 ГБ"},
    }

    max_thumb_size = 210
    thumb_heights = [130, 150, 185, 270]
    thumb_widths = [145, 145, 180, 230]
    pixmap_sizes = [50, 70, 100, 170]
    row_limits = [20, 20, 25, 32]
    corner_sizes = [4, 8, 14, 16]
    SPACING = 2
    OFFSET = 15


class JsonData:
    favs = {}
    show_hidden = False
    go_to_now = False
    dark_mode = None    
    show_text = False
    data_limit = len(Static.limit_mappings) -1

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
        if os.path.exists(Static.cfg_file):
            with open(Static.cfg_file, 'r', encoding="utf-8") as f:
                try:
                    json_data: dict = json.load(f)
                
                    for k, v in json_data.items():
                        if hasattr(cls, k):
                            setattr(cls, k, v)
                except json.JSONDecodeError:
                    print("Ошибка чтения json")
                    cls.write_json_data()
        else:
            print("файла cfg.json не существует")
            cls.write_json_data()

    @classmethod
    def write_json_data(cls):
        new_data: dict = {
            attr: getattr(cls, attr)
            for attr in cls.get_data()
        }

        try:
            with open(Static.cfg_file, 'w', encoding="utf-8") as f:
                json.dump(new_data, f, indent=4, ensure_ascii=False)
            return True
        
        except Exception as e:
            print(e)
            return False

    @classmethod
    def remove_files(cls):
        files = (
            "cfg.json",
            "db.db",
            "uti_icons",
            "log.txt",
            "servers.json",
            "thumbnails"
        )

        for i in os.scandir(Static.app_support):
            if i.name not in files:
                try:
                    if i.is_file():
                        os.remove(i.path)
                    else:
                        shutil.rmtree(i.path)
                except Exception as e:
                    print("cfg, do before start, error remove dir", e)

    @classmethod
    def init(cls):
        for i in (Static.app_support, Static.uti_icons):
            os.makedirs(i, exist_ok=True)
        cls.read_json_data()
        cls.write_json_data()
        cls.remove_files()


class Dynamic:
    rating_filter: int = 0
    word_filters: list[str] = []
    pixmap_size_ind = 2
    uti_filetype_qimage: dict = {}
    image_apps = []
