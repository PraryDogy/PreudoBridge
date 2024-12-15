import os
import subprocess
import sys
import traceback


class System_:

    @classmethod
    def catch_error_in_app(cls, exctype, value, tb) -> None:

        if exctype == RuntimeError:
            # в приложении мы игнорируем эту ошибку
            return

        ERROR = "".join(traceback.format_exception(exctype, value, tb))

        ABOUT = [
            "Отправьте это сообщение в telegram @evlosh",
            "или на почту loshkarev@miuz.ru"
        ]

        ABOUT = " ".join(ABOUT)

        STARS = "*" * 40


        SUMMARY_MSG = "\n".join([ERROR, STARS, ABOUT])
        
        script = "scripts/error_msg.scpt"
        subprocess.run(["osascript", script, SUMMARY_MSG])

    def catch_error_in_proj(exctype, value, tb):

        if exctype == RuntimeError:
            error_message = "".join(traceback.format_exception(exctype, value, tb))
            print(error_message)

        else:
            sys.__excepthook__(exctype, value, tb)

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


if System_.set_plugin_path():
    sys.excepthook = System_.catch_error_in_app
else:
    sys.excepthook = System_.catch_error_in_proj


from PyQt5.QtCore import QEvent, QObject
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
        JsonData.write_config()
        UThreadPool.stop_all()


print("sleep in grid standart")

JsonData.init()
Dbase.init_db()
app = CustomApp(sys.argv)

SignalsApp.init()
UThreadPool.init()
ex = SimpleFileExplorer()
ex.show()

# Запуск приложения
exit_code = app.exec()
