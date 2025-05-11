import subprocess

from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
                             QWidget)

from cfg import Static
from utils import Utils

from ._base_items import (MainWinItem, MinMaxDisabledWin, URunnable,
                          USvgSqareWidget, UThreadPool)



class WorkerSignals(QObject):
    finished_ = pyqtSignal()

class RemoveFilesTask(URunnable):
    def __init__(self, main_dir: str, urls: list[str]):
        super().__init__()
        self.signals_ = WorkerSignals()
        self.main_dir = main_dir
        self.urls = urls

    def task(self):
        try:
            command = ["osascript", Static.REMOVE_FILES_SCPT] + self.urls
            subprocess.run(command)
        except Exception as e:
            Utils.print_error(e)
        try:
            self.signals_.finished_.emit()
        except RuntimeError as e:
            Utils.print_error(e)



class RemoveFilesWin(MinMaxDisabledWin):
    finished_ = pyqtSignal(list)
    descr_text = "Переместить в корзину объекты"
    ok_text = "Ок"
    cancel_text = "Отмена"
    title_text = "Внимание!"
    svg_size = 50

    def __init__(self, main_win_item: MainWinItem, urls: list[str]):
        super().__init__()
        self.setWindowTitle(RemoveFilesWin.title_text)
        self.set_modality()
        self.urls = urls
        self.main_win_item = main_win_item

        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(10, 5, 10, 5)
        self.setLayout(v_lay)

        first_row_wid = QWidget()
        v_lay.addWidget(first_row_wid)
        first_row_lay = QHBoxLayout()
        first_row_lay.setContentsMargins(0, 0, 0, 0)
        first_row_wid.setLayout(first_row_lay)

        warn = USvgSqareWidget(Static.WARNING_SVG, RemoveFilesWin.svg_size)
        first_row_lay.addWidget(warn)

        t = f"{RemoveFilesWin.descr_text} ({len(urls)})?"
        question = QLabel(text=t)
        first_row_lay.addWidget(question)

        h_wid = QWidget()
        v_lay.addWidget(h_wid)
        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.setSpacing(10)
        h_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h_wid.setLayout(h_lay)

        ok_btn = QPushButton(RemoveFilesWin.ok_text)
        ok_btn.clicked.connect(self.cmd_)
        ok_btn.setFixedWidth(90)
        h_lay.addWidget(ok_btn)

        can_btn = QPushButton(RemoveFilesWin.cancel_text)
        can_btn.clicked.connect(self.deleteLater)
        can_btn.setFixedWidth(90)
        h_lay.addWidget(can_btn)

        self.adjustSize()
        self.setFixedSize(self.width(), self.height())

    def cmd_(self, *args):
        self.task_ = RemoveFilesTask(self.main_win_item.main_dir, self.urls)
        self.task_.signals_.finished_.connect(self.finalize)
        UThreadPool.start(runnable=self.task_)

    def finalize(self, *args):
        self.finished_.emit(self.urls)
        del self.task_
        self.deleteLater()

    def keyPressEvent(self, a0):
        if a0.key() == Qt.Key.Key_Escape:
            self.deleteLater()

        elif a0.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
            self.cmd_()
        return super().keyPressEvent(a0)
    