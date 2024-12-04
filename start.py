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
        
        script = "scripts/error_msg.scpt"
        subprocess.run(["osascript", script, SUMMARY_MSG])

    @classmethod
    def set_plugin_path(cls) -> bool:
        #lib folder appears when we pack this project to .app with py2app
        if os.path.exists("lib"): 
            ver = f"{sys.version_info.major}.{sys.version_info.minor}"
            plugin_path = f"lib/python{ver}/PyQt5/Qt5/plugins"
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
from gui import SimpleFileExplorer
from signals import SignalsApp
from utils import UThreadPool, Utils


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
        UThreadPool.stop_all()
        JsonData.write_config()


JsonData.init()
Dbase.init_db()
app = CustomApp(sys.argv)

SignalsApp.init()
UThreadPool.init()
ex = SimpleFileExplorer()
ex.show()

app.exec()
