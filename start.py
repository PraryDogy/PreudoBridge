import os
import sys
import traceback

from PyQt5.QtWidgets import (QApplication, QDialog, QPushButton, QTextEdit,
                             QVBoxLayout)


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

        d = QDialog()
        d.setWindowTitle("Ошибка")
        l = QVBoxLayout(d)

        txt = QTextEdit()
        txt.setReadOnly(True)
        txt.setPlainText(SUMMARY_MSG)
        l.addWidget(txt)

        l.addWidget(QPushButton("Закрыть", clicked=d.close))
        d.resize(500, 400)
        d.setFocus()
        d.exec_()

    def catch_error_in_proj(exctype, value, tb):
        if exctype == RuntimeError:
            try:
                frame = traceback.extract_tb(tb)[0]
                frame = f"{frame.filename}, line {frame.lineno}"
            except Exception:
                frame = ""
            print("Обработан RuntimeError:", frame)
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

# def trace_all_exceptions(frame, event, arg):
#     if event == "exception":
#         exc_type, exc_value, tb = arg
#         print(f"Перехвачено исключение: {exc_type.__name__}: {exc_value}")
#         traceback.print_tb(tb)
#     return trace_all_exceptions  # чтобы ловить дальше

# sys.settrace(trace_all_exceptions)



from PyQt5.QtCore import QEvent, QObject, Qt
from PyQt5.QtWidgets import QApplication

from cfg import Dynamic, JsonData
from system.database import Dbase
from system.items import BaseItem
from system.shared_utils import SharedUtils
from system.tasks import UThreadPool
from widgets._base_widgets import WinBase
from widgets.main_win import MainWin


class App(QApplication):
    def __init__(self, argv: list[str]) -> None:
        super().__init__(argv)

        self.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
        self.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

        JsonData.init()
        UThreadPool.init()
        Dbase.init()
        Dynamic.image_apps = SharedUtils.get_apps(JsonData.app_names)
        BaseItem.check_sortitem_attrs()

        self.main_win = MainWin()
        self.main_win.show()

        self.aboutToQuit.connect(lambda: self.main_win.on_exit())
        self.installEventFilter(self)

    def eventFilter(self, a0: QObject | None, a1: QEvent | None) -> bool:
        if a1.type() == QEvent.Type.ApplicationActivate:
            for i in WinBase.wins:
                i.show()
                i.raise_()
        return False

    def on_exit(self):
        JsonData.write_config()


app = App(argv=sys.argv)
app.exec()