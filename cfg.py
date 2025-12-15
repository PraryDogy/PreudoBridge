import glob
import json
import os


class Static:
    app_name = "PreudoBridge"
    app_ver = 3.70

    app_support = os.path.join(os.path.expanduser('~/Library/Application Support'), app_name)
    uti_icons = os.path.join(app_support, "uti_icons")
    thumbnails_dir = os.path.join(app_support, 'thumbnails')
    cfg_file = os.path.join(app_support, 'cfg.json')
    db_file = os.path.join(app_support, 'db.db')

    scripts_dir = "./scripts"
    in_app_icons_dir = "./icons"

    folder_type = "folder"
    rgba_gray = "rgba(128, 128, 128, 0.95)"
    rgba_blue = "rgb(70, 130, 240)"
    star_symbol = "\U00002605" # ★
    long_line_symbol = "\U00002014" # —
    paragraph_symbol = "\u2029" # символ PyQt5, который равен новой строке
    line_feed_symbol  = "\u000a" # символ PyQt5, который равен новой строке
    hidden_symbols = (".", "~$", "$")

    app_exts = (".app", ".APP")

    ww, hh = 1120, 760

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

    image_apps = []

    max_thumb_size = 210
    thumb_heights = [130, 150, 185, 270]
    thumb_widths = [145, 145, 180, 230]
    pixmap_sizes = [50, 70, 100, 170]
    row_limits = [20, 20, 25, 32]
    corner_sizes = [4, 8, 14, 16]
    SPACING = 2
    OFFSET = 15

    @classmethod
    def get_image_apps(cls):
        patterns = [
            "/Applications/Adobe Photoshop*/*.app",
            "/Applications/Adobe Photoshop*.app",
            "/Applications/Capture One*/*.app",
            "/Applications/Capture One*.app",
            "/Applications/ImageOptim.app",
            "/System/Applications/Preview.app",
            "/System/Applications/Photos.app",
        ]

        apps = []
        for pat in patterns:
            for path in glob.glob(pat):
                if path not in apps:
                    apps.append(path)

        apps.sort(key=os.path.basename)
        return apps



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
            with open(Static.cfg_file, 'w', encoding="utf-8") as f:
                json.dump(new_data, f, indent=4, ensure_ascii=False)
            return True
        
        except Exception as e:
            print(e)
            return False

    @classmethod
    def setup_icons(cls):
        os.makedirs(Static.uti_icons, exist_ok=True)

    @classmethod
    def do_before_start(cls):
        ...

    @classmethod
    def init(cls):
        Static.image_apps = Static.get_image_apps()
        os.makedirs(Static.app_support, exist_ok=True)
        cls.read_json_data()
        cls.write_config()
        try:
            cls.do_before_start()
        except Exception as e:
            print("do before start", e)
        cls.setup_icons()

class Dynamic:
    rating_filter: int = 0
    word_filters: list[str] = []
    pixmap_size_ind = 2
    uti_qimage: dict = {}