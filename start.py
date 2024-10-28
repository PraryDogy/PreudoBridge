import os
import sys
import traceback

from PyQt5.QtWidgets import QApplication, QMessageBox, QPushButton


def catch_err(exc_type, exc_value, exc_traceback):
    error_message = "".join(
        traceback.format_exception(exc_type, exc_value, exc_traceback)
        )
    error_dialog(error_message)


def error_dialog(error_message):
    error_dialog = QMessageBox()
    error_dialog.setIcon(QMessageBox.Critical)
    error_dialog.setWindowTitle("Error / Ошибка")

    tt = "\n".join(
        ["Отправьте ошибку / Send error", "email: loshkarev@miuz.ru", "tg: evlosh"]
        )
    error_dialog.setText(tt)
    error_dialog.setDetailedText(error_message)

    exit_button = QPushButton("Выход")
    exit_button.clicked.connect(QApplication.quit)
    error_dialog.addButton(exit_button, QMessageBox.ActionRole)

    error_dialog.exec_()


#lib folder appears when we pack this project to .app with py2app
if os.path.exists("lib"): 

    # setup pyqt5 plugin path BEFORE create QApplication
    # relative path in .app
    plugin_path = "lib/python3.11/PyQt5/Qt5/plugins"
    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = plugin_path

    # catch any unexcepted error with pyqt5 dialog box
    sys.excepthook = catch_err


from PyQt5.QtCore import QLibraryInfo, QTranslator
from PyQt5.QtWidgets import QApplication

from database import Dbase
from gui import CustomApp, SimpleFileExplorer

Dbase.init_db()

app = CustomApp(sys.argv)

translator = QTranslator()
locale = "ru_RU"

if translator.load(f"qtbase_{locale}", QLibraryInfo.location(QLibraryInfo.TranslationsPath)):
    app.installTranslator(translator)

ex = SimpleFileExplorer()
ex.show()
sys.exit(app.exec_())
