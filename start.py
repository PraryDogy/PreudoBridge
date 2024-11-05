import os
import subprocess
import sys
import traceback


class System_:

    @classmethod
    def catch_error(cls, *args) -> None:

        STARS = "*" * 40
        ABOUT = "Отправьте это сообщение в telegram @evlosh или на почту loshkarev@miuz.ru"
        ERROR = traceback.format_exception(*args)

        SUMMARY_MSG = "\n".join([*ERROR, STARS, ABOUT])
        APP_NAME: str = "MiuzCollections"

        FILE_: str = os.path.join(
            os.path.expanduser("~"),
            "Library",
            "Application Support",
            APP_NAME + "QT",
            "error.txt"
            )

        with open(FILE_, "w")as f:
            f.write(SUMMARY_MSG)

        subprocess.run(["open", FILE_])

    @classmethod
    def set_plugin_path(cls) -> bool:
        #lib folder appears when we pack this project to .app with py2app
        if os.path.exists("lib"): 
            plugin_path = "lib/python3.11/PyQt5/Qt5/plugins"
            os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = plugin_path
            return True
        else:
            return False
        
    @classmethod
    def set_excepthook(cls) -> None:
        sys.excepthook = cls.catch_error


if System_.set_plugin_path():
    System_.set_excepthook()


from PyQt5.QtCore import QEvent, QLibraryInfo, QObject, QTranslator
from PyQt5.QtWidgets import QApplication

from cfg import JsonData
from database import Dbase
from utils import Utils


class CustomApp(QApplication):
    def __init__(self, argv: list[str]) -> None:
        super().__init__(argv)
        self.aboutToQuit.connect(self.on_exit)
        self.installEventFilter(self)

    def eventFilter(self, a0: QObject | None, a1: QEvent | None) -> bool:
        if a1.type() == QEvent.Type.ApplicationActivate:
            Utils.get_main_win().show()
        return False

    def on_exit(self):
        JsonData.write_config()

from gui import SimpleFileExplorer

JsonData.read_json_data()
JsonData.find_img_apps()
Dbase.init_db()

app = CustomApp(sys.argv)

translator = QTranslator()
locale = "ru_RU"
if translator.load(f"qtbase_{locale}", QLibraryInfo.location(QLibraryInfo.TranslationsPath)):
    app.installTranslator(translator)

ex = SimpleFileExplorer()
ex.show()

app.exec()
