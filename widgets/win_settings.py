
import os
import shutil
import subprocess
import webbrowser

from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QKeyEvent
from PyQt5.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton,
                             QVBoxLayout, QWidget)

from cfg import HASH_DIR, JSON_FILE, LINK, JsonData
from database import Dbase
from signals import SignalsApp
from utils import URunnable, UThreadPool, Utils

from ._base import WinMinMax

LOADING_T = "Вычисляю"
DATA_T = "Данные"
SETTINGS_T = "Настройки"
CLEAR_T = "Очистить"
JSON_T = "Json"
UPDATE_T = "Обновления"


class WorkerSignals(QObject):
    finished_ = pyqtSignal(str)


class GetSizer(URunnable):
    def __init__(self):
        super().__init__()
        self.signals_ = WorkerSignals()

    @URunnable.set_running_state
    def run(self):
        total_size = 0

        if os.path.exists(HASH_DIR):

            for root, dirs, files in os.walk(HASH_DIR):

                if not self.should_run:
                    return

                for file in files:

                    if not self.should_run:
                        return
                
                    file_path = os.path.join(root, file)
                    total_size += os.path.getsize(file_path)

        data_size = DATA_T
        total_size = Utils.get_f_size(total_size)
        t = f"{data_size}: {total_size}"       
        self.signals_.finished_.emit(t)


class WinSettings(WinMinMax):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle(SETTINGS_T)
        self.setFixedSize(270, 120)

        main_lay = QVBoxLayout()
        main_lay.setContentsMargins(10, 10, 10, 10)
        main_lay.setSpacing(10)
        self.setLayout(main_lay)

        h_wid = QWidget()
        main_lay.addWidget(h_wid)

        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_wid.setLayout(h_lay)

        self.current_size = QLabel("")
        h_lay.addWidget(self.current_size)

        self.clear_btn = QPushButton(CLEAR_T)
        self.clear_btn.setFixedWidth(110)
        self.clear_btn.clicked.connect(self.clear_db_cmd)
        h_lay.addWidget(self.clear_btn)
        
        separator = QFrame()
        separator.setFixedWidth(self.width() - 40)
        separator.setFrameShape(QFrame.HLine)  # Горизонтальный разделитель
        separator.setFrameShadow(QFrame.Sunken)  # Внешний вид (утопленный)
        main_lay.addWidget(separator, alignment=Qt.AlignmentFlag.AlignCenter)

        h_wid = QWidget()
        main_lay.addWidget(h_wid)
        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_wid.setLayout(h_lay)

        open_json_btn = QPushButton(JSON_T)
        open_json_btn.setFixedWidth(110)
        open_json_btn.clicked.connect(lambda: subprocess.call(["open", JSON_FILE]))
        h_lay.addWidget(open_json_btn)

        open_json_btn = QPushButton(UPDATE_T)
        open_json_btn.setFixedWidth(110)
        open_json_btn.clicked.connect(lambda: webbrowser.open(LINK))
        h_lay.addWidget(open_json_btn)

        main_lay.addStretch()

        self.get_current_size()

    def get_current_size(self):
        self.current_size.setText(LOADING_T)

        self.task_ = GetSizer()
        cmd_ = lambda t: self.current_size.setText(t)
        self.task_.signals_.finished_.connect(cmd_)
        UThreadPool.start(self.task_)

    def clear_db_cmd(self):
        Dbase.clear_db()            
        if os.path.exists(HASH_DIR):
            shutil.rmtree(HASH_DIR)
        self.get_current_size()
        SignalsApp.all_.load_standart_grid.emit("")

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        if hasattr(self, "task_") and self.task_.is_running:
            self.task_.should_run = False
        JsonData.write_config()
    
    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() == Qt.Key.Key_Escape:
            self.close()