import os
import shutil
import subprocess
from datetime import datetime

from PyQt5.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QKeyEvent
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import (QGroupBox, QHBoxLayout, QLabel, QPushButton,
                             QVBoxLayout, QWidget)

from cfg import JsonData, Static
from utils import URunnable, UThreadPool

from ._base_widgets import MinMaxDisabledWin

LOADING_T = "Вычисляю"
DATA_T = "Данные"
SETTINGS_T = "Настройки"
CLEAR_T = "Очистить"
JSON_T = "Json"
UPDATE_T = "Обновления"
UPDATE_WAIT_T = "Подождите"
UPDATE_ERROR_T = "Ошибка"
JSON_DESCR = "Открыть текстовый файл настроек"
UPDATE_DESCR = "Скачать обновления"
UPDATE_DESCR_ERR = "Нет подключения к диску"
LEFT_W = 110
ICON_W = 70
CLEAR_DATA_T = "Очистить"
CLEAR_DATA_DESCR = "Очистить данные в этой папке"

ABOUT_T = "\n".join(
    [
        f"{Static.APP_NAME} {Static.APP_VER}",
        f"{datetime.now().year} Evgeny Loshakev"
    ]
)


class ClearData(QGroupBox):
    clear_data_clicked = pyqtSignal()

    def __init__(self):
        super().__init__()

        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        self.setLayout(h_lay)

        btn_ = QPushButton(text=CLEAR_DATA_T)
        btn_.clicked.connect(self.clear_data_clicked.emit)
        btn_.setFixedWidth(LEFT_W)
        h_lay.addWidget(btn_)

        descr = QLabel(text=CLEAR_DATA_DESCR)
        h_lay.addWidget(descr)


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


class WorkerSignals(QObject):
    finished_ = pyqtSignal(bool)


class DownloadUpdate(URunnable):
    def __init__(self):
        super().__init__()
        self.signals_ = WorkerSignals()

    def run(self):
        for i in JsonData.udpdate_file_paths:
            if os.path.exists(i):

                dest = shutil.copy2(
                    src=i,
                    dst=os.path.expanduser("~/Downloads")
                )
                subprocess.run(["open", "-R", dest])
                self.signals_.finished_.emit(True)
                return

        self.signals_.finished_.emit(False)


class Updates(QGroupBox):
    def __init__(self):
        super().__init__()

        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        self.setLayout(h_lay)

        self.btn_ = QPushButton(text=UPDATE_T)
        self.btn_.setFixedWidth(LEFT_W)
        self.btn_.clicked.connect(self.update_cmd)

        h_lay.addWidget(self.btn_)

        self.descr = QLabel(text=UPDATE_DESCR)
        h_lay.addWidget(self.descr)

    def update_cmd(self, *args):
        self.btn_.setText(UPDATE_WAIT_T)
        self.task_ = DownloadUpdate()
        self.task_.signals_.finished_.connect(self.update_cmd_fin)
        UThreadPool.start(runnable=self.task_)

    def update_cmd_fin(self, arg: bool):
        if arg:
            self.btn_.setText(UPDATE_T)
        else:
            self.btn_.setText(UPDATE_ERROR_T)
            self.descr.setText(UPDATE_DESCR_ERR)
            QTimer.singleShot(1500, lambda: self.btn_.setText(UPDATE_T))
            QTimer.singleShot(1500, lambda: self.descr.setText(UPDATE_DESCR))


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


class SettingsWin(MinMaxDisabledWin):
    clear_data_clicked = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle(SETTINGS_T)

        main_lay = QVBoxLayout()
        main_lay.setContentsMargins(10, 0, 10, 15)
        self.setLayout(main_lay)

        h_wid = QWidget()
        main_lay.addWidget(h_wid)

        clear_data_wid = ClearData()
        clear_data_wid.clear_data_clicked.connect(self.clear_data_clicked.emit)
        main_lay.addWidget(clear_data_wid)

        json_wid = JsonFile()
        main_lay.addWidget(json_wid)

        updates_wid = Updates()
        main_lay.addWidget(updates_wid)

        about_wid = About()
        main_lay.addWidget(about_wid)

        self.adjustSize()
        self.setFixedSize(self.width() + 30, self.height())

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        if hasattr(self, "task_") and self.task_.is_running:
            self.task_.should_run = False
        JsonData.write_config()
    
    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() == Qt.Key.Key_Escape:
            self.close()