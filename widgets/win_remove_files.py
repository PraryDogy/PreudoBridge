import subprocess

from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
                             QWidget)

from cfg import Static
from utils import URunnable, UThreadPool

from ._base_widgets import USvgSqareWidget, WinMinMaxDisabled

REMOVE_T = "Удалить безвозвратно объекты"
OK_T = "Ок"
CANCEL_T = "Отмена"
ATTENTION_T = "Внимание!"


class WorkerSignals(QObject):
    finished_ = pyqtSignal()
    load_st_grid_sig = pyqtSignal(tuple)


class RemoveFilesTask(URunnable):
    def __init__(self, main_dir: str, urls: list[str]):
        super().__init__()
        self.signals_ = WorkerSignals()
        self.main_dir = main_dir
        self.urls = urls

    @URunnable.set_running_state
    def run(self):
        try:
            subprocess.run(["rm", "-rf"] + self.urls, check=True)
            self.signals_.load_st_grid_sig.emit((self.main_dir, None))
            self.signals_.finished_.emit()

        except Exception as e:
            ...


class WinRemoveFiles(WinMinMaxDisabled):
    load_st_grid_sig = pyqtSignal(tuple)

    def __init__(self, main_dir: str, urls: list[str]):
        super().__init__()
        self.setWindowTitle(ATTENTION_T)
        self.urls = urls
        self.main_dir = main_dir

        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(10, 5, 10, 5)
        self.setLayout(v_lay)

        first_row_wid = QWidget()
        v_lay.addWidget(first_row_wid)
        first_row_lay = QHBoxLayout()
        first_row_lay.setContentsMargins(0, 0, 0, 0)
        first_row_wid.setLayout(first_row_lay)

        warn = USvgSqareWidget(src=Static.WARNING_SVG, size=50)
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
        self.task_ = RemoveFilesTask(self.main_dir, self.urls)
        self.task_.signals_.load_st_grid_sig.connect(self.load_st_grid_sig.emit)
        self.task_.signals_.finished_.connect(self.finalize)
        UThreadPool.start(runnable=self.task_)

    def finalize(self, *args):
        del self.task_
        self.close()

    def keyPressEvent(self, a0):
        if a0.key() == Qt.Key.Key_Escape:
            self.close()

        elif a0.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
            self.cmd_()
        return super().keyPressEvent(a0)