
import os
import shutil
import subprocess
import webbrowser

from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QKeyEvent
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import (QSpacerItem, QGroupBox, QHBoxLayout, QLabel,
                             QPushButton, QVBoxLayout, QWidget)

from cfg import JsonData, Static
from database import Dbase
from signals import SignalsApp
from utils import URunnable, UThreadPool, Utils
from datetime import datetime

from ._base import WinMinMax

LOADING_T = "Вычисляю"
DATA_T = "Данные"
SETTINGS_T = "Настройки"
CLEAR_T = "Очистить"
JSON_T = "Json"
UPDATE_T = "Обновления"
JSON_DESCR = "Открыть текстовый файл настроек"
UPDATE_DESCR = "Обновления на Яндекс Диске"
LEFT_W = 110
ICON_W = 70

ABOUT_T = "\n".join(
    [
        f"{Static.APP_NAME} {Static.APP_VER}",
        f"{datetime.now().year} Evgeny Loshakev"
    ]
)


class JsonFile(QGroupBox):
    def __init__(self):
        super().__init__()

        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        self.setLayout(h_lay)

        btn_ = QPushButton(text=JSON_T)
        btn_.setFixedWidth(LEFT_W)
        btn_.clicked.connect(
            lambda: subprocess.call(["open", Static.JSON_FILE])
        )
        h_lay.addWidget(btn_)

        descr = QLabel(text=JSON_DESCR)
        h_lay.addWidget(descr)


class Updates(QGroupBox):
    def __init__(self):
        super().__init__()

        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        self.setLayout(h_lay)

        btn_ = QPushButton(text=UPDATE_T)
        btn_.setFixedWidth(LEFT_W)
        btn_.clicked.connect(lambda: webbrowser.open(Static.LINK))

        h_lay.addWidget(btn_)

        descr = QLabel(text=UPDATE_DESCR)
        h_lay.addWidget(descr)


class About(QGroupBox):
    def __init__(self):
        super().__init__()

        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        self.setLayout(h_lay)

        svg_ = QSvgWidget()
        svg_.load(Static.ICON_SVG)
        svg_.setFixedSize(ICON_W, ICON_W)
        h_lay.addWidget(svg_)

        descr = QLabel(ABOUT_T)
        h_lay.addWidget(descr)


class WinSettings(WinMinMax):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle(SETTINGS_T)

        main_lay = QVBoxLayout()
        main_lay.setContentsMargins(10, 0, 10, 15)
        self.setLayout(main_lay)

        h_wid = QWidget()
        main_lay.addWidget(h_wid)

        json_row = JsonFile()
        main_lay.addWidget(json_row)

        updates_row = Updates()
        main_lay.addWidget(updates_row)

        about_row = About()
        main_lay.addWidget(about_row)

        self.adjustSize()
        self.setFixedSize(self.width() + 30, self.height())

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        if hasattr(self, "task_") and self.task_.is_running:
            self.task_.should_run = False
        JsonData.write_config()
    
    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() == Qt.Key.Key_Escape:
            self.close()