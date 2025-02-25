import os
import shutil
import subprocess

from PyQt5.QtCore import QObject, QRunnable, Qt, pyqtSignal
from PyQt5.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
                             QWidget)

from cfg import Dynamic, JsonData, Static
from signals import SignalsApp
from utils import URunnable, UThreadPool

from ._base import WinMinMax

REMOVE_T = "Удалить безвозвратно выделенные объекты?"
OK_T = "Ок"
CANCEL_T = "Отмена"
ATTENTION_T = "Внимание!"

class WorkerSignals(QObject):
    finished_ = pyqtSignal()


class DeleteFilesTask(URunnable):
    def __init__(self, urls: list[str]):
        super().__init__()
        self.urls = urls

    @URunnable.set_running_state
    def run(self):
        subprocess.run(["rm", "-rf"] + self.urls, check=True)
        SignalsApp.instance.load_standart_grid_cmd(
            path=JsonData.root,
            prev_path=None
        )


class WinRemoveFiles(WinMinMax):
    finished_ = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setFixedSize(310, 80)
        self.setWindowTitle(ATTENTION_T)

        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(10, 10, 10, 10)
        v_lay.setSpacing(10)
        self.setLayout(v_lay)

        question = QLabel(text=REMOVE_T)
        v_lay.addWidget(question)

        h_wid = QWidget()
        v_lay.addWidget(h_wid)
        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h_wid.setLayout(h_lay)

        ok_btn = QPushButton(text=OK_T)
        ok_btn.setFixedWidth(100)
        h_lay.addWidget(ok_btn)

        can_btn = QPushButton(text=CANCEL_T)
        can_btn.clicked.connect(self.close)
        can_btn.setFixedWidth(100)
        h_lay.addWidget(can_btn)

    def keyPressEvent(self, a0):
        if a0.key() == Qt.Key.Key_Escape:
            self.close()
        return super().keyPressEvent(a0)