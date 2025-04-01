import subprocess

from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
                             QWidget)
from cfg import JsonData, Static
from signals import SignalsApp
from utils import URunnable, UThreadPool

from ._base import WinMinMax, USvgWidget

REMOVE_T = "Удалить безвозвратно объекты"
OK_T = "Ок"
CANCEL_T = "Отмена"
ATTENTION_T = "Внимание!"


class WorkerSignals(QObject):
    finished_ = pyqtSignal()


class RemoveFilesTask(URunnable):
    def __init__(self, urls: list[str]):
        super().__init__()
        self.signals_ = WorkerSignals()
        self.urls = urls

    @URunnable.set_running_state
    def run(self):
        try:
            subprocess.run(["rm", "-rf"] + self.urls, check=True)

            SignalsApp.instance.load_standart_grid_cmd(
                path=JsonData.root,
                prev_path=None
            )
            
            self.signals_.finished_.emit()

        except Exception as e:
            ...


class WinRemoveFiles(WinMinMax):
    def __init__(self, urls: list[str]):
        super().__init__()
        # self.setFixedSize(250, 70)
        self.setWindowTitle(ATTENTION_T)

        self.urls = urls

        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(10, 5, 10, 5)
        # v_lay.setSpacing(5)
        self.setLayout(v_lay)

        first_row_wid = QWidget()
        v_lay.addWidget(first_row_wid)
        first_row_lay = QHBoxLayout()
        first_row_lay.setContentsMargins(0, 0, 0, 0)
        first_row_wid.setLayout(first_row_lay)

        warn = USvgWidget(src=Static.WARNING_SVG, size=50)
        first_row_lay.addWidget(warn)

        t = f"{REMOVE_T} ({len(urls)})?"
        question = QLabel(text=t)
        first_row_lay.addWidget(question)

        h_wid = QWidget()
        v_lay.addWidget(h_wid)
        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.setSpacing(10)
        h_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h_wid.setLayout(h_lay)

        ok_btn = QPushButton(text=OK_T)
        ok_btn.clicked.connect(self.cmd_)
        ok_btn.setFixedWidth(90)
        h_lay.addWidget(ok_btn)

        can_btn = QPushButton(text=CANCEL_T)
        can_btn.clicked.connect(self.close)
        can_btn.setFixedWidth(90)
        h_lay.addWidget(can_btn)

        self.adjustSize()
        self.setFixedSize(self.width(), self.height())

    def cmd_(self, *args):
        self.task_ = RemoveFilesTask(urls=self.urls)
        self.task_.signals_.finished_.connect(self.finalize)
        UThreadPool.start(runnable=self.task_)

    def finalize(self, *args):
        del self.task_
        self.close()

    def keyPressEvent(self, a0):
        if a0.key() == Qt.Key.Key_Escape:
            self.close()
        return super().keyPressEvent(a0)