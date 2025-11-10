import json
import os


class Static:
    app_name = "PreudoBridge"
    app_ver = 3.65

    app_support = os.path.join(os.path.expanduser('~/Library/Application Support'), app_name)
    ext_icons_dir = os.path.join(app_support, "icons")
    thumbnails_dir = os.path.join(app_support, 'thumbnails')
    cfg_file = os.path.join(app_support, 'cfg.json')
    db_file = os.path.join(app_support, 'db.db')

    scripts_dir = "scripts"
    app_icons_dir = "icons"

    folder_type = "folder"
    rgba_gray = "rgba(128, 128, 128, 0.95)"
    rgba_blue = "rgb(70, 130, 240)"
    star_symbol = "\U00002605" # ★
    long_line_symbol = "\U00002014" # —
    paragraph_symbol = "\u2029" # символ PyQt5, который равен новой строке
    line_feed_symbol  = "\u000a" # символ PyQt5, который равен новой строке
    hidden_symbols = (".", "~$", "$")

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

    preloaded_icons = {
        **{ext: os.path.join("icons", "excel.svg") for ext in excel_ext},
        **{ext: os.path.join("icons", "word.svg") for ext in word_ext},
        **{ext: os.path.join("icons", "ppt.svg") for ext in ppt_ext},
        **{ext: os.path.join("icons", "pdf.svg") for ext in pdf_ext},
        **{ext: os.path.join("icons", "archive.svg") for ext in archive_ext},
        **{ext: os.path.join("icons", "audio.svg") for ext in audio_ext},
        **{ext: os.path.join("icons", "ai.svg") for ext in ai_ext},
        **{ext: os.path.join("icons", "indd.svg") for ext in indd_ext},
        **{ext: os.path.join("icons", "db.svg") for ext in db_ext},
    }

    limit_mappings = {
        0: {"bytes": 200 * 1024 * 1024, "text": "200 МБ"},
        1: {"bytes": 500 * 1024 * 1024, "text": "500 МБ"},
        2: {"bytes": 1000 * 1024 * 1024, "text": "1 ГБ"},
        3: {"bytes": 2000 * 1024 * 1024, "text": "2 ГБ"},
        4: {"bytes": 5000 * 1024 * 1024, "text": "5 ГБ"},
        5: {"bytes": 10000 * 1024 * 1024, "text": "10 ГБ"},
    }

    image_apps = [
        "/Applications/Adobe Photoshop 2025/Adobe Photoshop 2025.app",
        "/Applications/Adobe Photoshop 2024/Adobe Photoshop 2024.app",
        "/Applications/Adobe Photoshop 2023/Adobe Photoshop 2023.app",
        "/Applications/Adobe Photoshop 2022/Adobe Photoshop 2022.app",
        "/Applications/Adobe Photoshop 2021/Adobe Photoshop 2021.app",
        "/Applications/Adobe Photoshop 2020/Adobe Photoshop 2020.app",
        "/Applications/Adobe Photoshop CC 2019/Adobe Photoshop CC 2019.app",
        "/Applications/Adobe Photoshop CC 2018/Adobe Photoshop CC 2018.app",
        "/Applications/Adobe Photoshop CC 2017/Adobe Photoshop CC 2017.app",
        "/Applications/Adobe Photoshop.app",
        "/Applications/Capture One 25.app",
        "/Applications/Capture One 24.app",
        "/Applications/Capture One 23.app",
        "/Applications/Capture One 22.app",
        "/Applications/Capture One 21.app",
        "/Applications/Capture One 20.app",
        "/Applications/Capture One 12.app",
        "/Applications/Capture One 11.app",
        "/Applications/Capture One.app",
        "/Applications/ImageOptim.app",
        "/System/Applications/Preview.app",
        "/System/Applications/Photos.app"
    ]
    image_apps = [i for i in image_apps if os.path.exists(i)]

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
        os.makedirs(Static.ext_icons_dir, exist_ok=True)

    @classmethod
    def do_before_start(cls):
        ...

    @classmethod
    def init(cls):
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
    pixmap_size_ind = 0
