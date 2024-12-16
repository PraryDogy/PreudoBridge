
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
JSON_DESCR = "Открыть файл настроек .json"
UPDATE_DESCR = "Обновления на Яндекс Диске"
LEFT_W = 110
ICON_W = 70

ABOUT_T = "\n".join(
    [
        f"{Static.APP_NAME} {Static.APP_VER}",
        f"{datetime.now().year} Evgeny Loshakev"
    ]
)


class WorkerSignals(QObject):
    finished_ = pyqtSignal(str)


class GetSizer(URunnable):
    def __init__(self):
        super().__init__()
        self.signals_ = WorkerSignals()

    @URunnable.set_running_state
    def run(self):
        try:
            self.main()
        except RuntimeError as e:
            Utils.print_error(parent=None, error=e)

    def main(self):

        if not os.path.exists(Static.HASH_DIR):
            return

        total_size = 0
        stack = []
        stack.append(Static.HASH_DIR)

        while stack:
            current_dir = stack.pop()

            with os.scandir(current_dir) as entries:

                for entry in entries:

                    if not self.should_run:
                        return

                    if entry.is_dir():
                        stack.append(entry.path)

                    else:
                        try:
                            total_size += entry.stat().st_size
                        except Exception:
                            ...

        data_size = DATA_T
        total_size = Utils.get_f_size(total_size)
        t = f"{data_size}: {total_size}"       
        self.signals_.finished_.emit(t)


class DataRow(QGroupBox):
    clicked_ = pyqtSignal()

    def __init__(self):
        super().__init__()

        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        self.setLayout(h_lay)

        btn_ = QPushButton(text=CLEAR_T)
        btn_.setFixedWidth(LEFT_W)
        btn_.clicked.connect(self.clicked_.emit)

        h_lay.addWidget(btn_)

        self.descr = QLabel(text=UPDATE_DESCR)
        h_lay.addWidget(self.descr)


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
        main_lay.setContentsMargins(10, 10, 10, 10)
        self.setLayout(main_lay)

        h_wid = QWidget()
        main_lay.addWidget(h_wid)

        self.data_row = DataRow()
        self.data_row.clicked_.connect(self.clear_db_cmd)
        main_lay.addWidget(self.data_row)

        json_row = JsonFile()
        main_lay.addWidget(json_row)

        updates_row = Updates()
        main_lay.addWidget(updates_row)

        about_row = About()
        main_lay.addWidget(about_row)

        self.adjustSize()
        self.setFixedSize(self.width() + 30, self.height())
        self.get_current_size()

    def get_current_size(self):
        self.data_row.descr.setText(LOADING_T)

        self.task_ = GetSizer()
        cmd_ = lambda t: self.data_row.descr.setText(t)
        self.task_.signals_.finished_.connect(cmd_)
        UThreadPool.start(self.task_)

    def clear_db_cmd(self):
        Dbase.clear_db()            
        if os.path.exists(Static.HASH_DIR):
            shutil.rmtree(Static.HASH_DIR)
        self.get_current_size()
        SignalsApp.all_.load_standart_grid.emit("")

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        if hasattr(self, "task_") and self.task_.is_running:
            self.task_.should_run = False
        JsonData.write_config()
    
    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() == Qt.Key.Key_Escape:
            self.close()