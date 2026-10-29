import json
import os
import sys


def _resource_root() -> str:
    """
    Папка с ресурсами (images, scripts).
    Относительные пути "./images" работают только если CWD совпадает с папкой
    приложения. Из Finder CWD чаще всего "/", поэтому считаем путь явно.
    """
    if getattr(sys, "frozen", False):
        # py2app: .../Contents/MacOS/<app> -> .../Contents/Resources
        return os.path.abspath(
            os.path.join(os.path.dirname(sys.executable), "..", "Resources")
        )
    return os.path.dirname(os.path.abspath(__file__))


_RESOURCE_ROOT = _resource_root()


class Themes:
    macos = "macos"
    dark = "dark"
    light = "light"


class Static:
    app_name = "PreudoBridge"
    app_ver = 6.6

    app_dir = os.path.join(os.path.expanduser('~/Library/Application Support'), app_name)
    external_thumbs_dir = os.path.join(app_dir, 'thumbnails')
    external_json = os.path.join(app_dir, 'cfg.json')
    external_db = os.path.join(app_dir, 'db.db')

    internal_scpt_dir = os.path.join(_RESOURCE_ROOT, "scripts")
    internal_images_dir = os.path.join(_RESOURCE_ROOT, "images")

    folder_type = "Папка"
    rgba_blue = "rgb(70, 130, 240)"
    star_symbol = "\U00002605"  # ★
    long_line_symbol = "\U00002014"  # —
    paragraph_symbol = "\u2029"  # символ PyQt6, который равен новой строке
    line_feed_symbol = "\u000a"  # символ PyQt6, который равен новой строке
    hidden_symbols = (".", "~$", "$")
    base_ww, base_hh = 1120, 760
    max_thumb_size = 210

    # размеры для QPixmap в виджете Thumb
    thumb_widget_pixmap_size = [65, 80, 165]
    # рамка вокруг QPixmap в виджете Thumb
    img_wid_border = 10
    # дополнительное пространство к ширине виджета Thumb
    thumb_widget_extra_w = 40


class JsonData:
    favs = {}
    go_to_now = False
    show_text = False
    theme = Themes.macos

    @classmethod
    def get_data(cls):
        return [
            i for i in dir(cls)
            if not i.startswith("__")
            and not callable(getattr(cls, i))
        ]

    @classmethod
    def read_json_data(cls):
        if not os.path.exists(Static.external_json):
            print("файла cfg.json не существует")
            cls.write_json_data()
            return

        try:
            with open(Static.external_json, "r", encoding="utf-8") as f:
                json_data = json.load(f)
        except (json.JSONDecodeError, OSError):
            print("Ошибка чтения json, испорченный файл сохранен как .broken")
            try:
                os.replace(Static.external_json, Static.external_json + ".broken")
            except OSError:
                pass
            cls.write_json_data()
            return

        if not isinstance(json_data, dict):
            return

        for k, v in json_data.items():
            # не даем JSON перезаписать методы и служебные атрибуты
            if k.startswith("_") or not hasattr(cls, k):
                continue
            if callable(getattr(cls, k)):
                continue
            setattr(cls, k, v)

    @classmethod
    def write_json_data(cls):
        new_data: dict = {
            attr: getattr(cls, attr)
            for attr in cls.get_data()
        }

        try:
            os.makedirs(Static.app_dir, exist_ok=True)
            with open(Static.external_json, 'w', encoding="utf-8") as f:
                json.dump(new_data, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(e)
            return False

    @classmethod
    def init(cls):
        cls.read_json_data()
        cls.write_json_data()


class Dynamic:
    word_filters: list[str] = []
    current_pixmap_size_index = 1
    image_apps: list[str] = []
