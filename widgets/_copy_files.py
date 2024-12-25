import os
import shutil

from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from cfg import JsonData
from signals import SignalsApp
from utils import URunnable, UThreadPool

# URUNNABLE # URUNNABLE # URUNNABLE # URUNNABLE # URUNNABLE # URUNNABLE # URUNNABLE 

COPY_T = "Копирую"
FROM_T = "из"
PREPARING_T = "Подготовка..."
CANCEL_T = "Отмена"


class WorkerSignals(QObject):
    progress = pyqtSignal(str)
    finished_ = pyqtSignal(int)


class FileMoverThread(URunnable):

    def __init__(self, items: list, dest: str):

        super().__init__()

        self.signals_ = WorkerSignals()

        self.items = items
        self.dest = dest
        self.counter = 0

    @URunnable.set_running_state
    def run(self):
        total_items = len(self.items)
        for index, item in enumerate(self.items, start=1):

            if not self.should_run:
                self.signals_.finished_.emit(self.counter)
                return

            try:
                path = os.path.join(self.dest, os.path.basename(item))
                shutil.copy(item, path)
                self.counter += 1

            except (shutil.SameFileError, IsADirectoryError):
                 ...

            t = f"{COPY_T} {index} {FROM_T} {total_items}"
            self.signals_.progress.emit(t)

        self.signals_.finished_.emit(self.counter)


class WinCopyFiles(QWidget):
    def __init__(self, items: list, dest: str, title: str):
        super().__init__()

        self.setWindowTitle(title)
        self.setFixedSize(250, 60)

        fl = Qt.WindowType.Window | Qt.WindowType.CustomizeWindowHint
        fl = fl  | Qt.WindowType.WindowCloseButtonHint
        self.setWindowFlags(fl)

        h_lay = QHBoxLayout(self)
        h_lay.setContentsMargins(15, 0, 15, 0)
        self.setLayout(h_lay)

        self.progress_label = QLabel(text=PREPARING_T)
        h_lay.addWidget(self.progress_label)

        self.cancel_button = QPushButton(text=CANCEL_T)
        self.cancel_button.setFixedWidth(100)
        self.cancel_button.clicked.connect(self.close_thread)
        h_lay.addWidget(self.cancel_button)

        self.task_ = FileMoverThread(
            items=items,
            dest=dest
        )

        self.task_.signals_.progress.connect(self.update_progress)
        self.task_.signals_.finished_.connect(self.on_finished)

        UThreadPool.start(runnable=self.task_)

    def update_progress(self, text: str):
        self.progress_label.setText(text)

    def on_finished(self, counter: int):

        if counter > 0:

            SignalsApp.instance.load_standart_grid_cmd(
                path=JsonData.root,
                prev_path=None
            )

        QTimer.singleShot(1000, self.close)

    def close_thread(self, *args):
        self.task_.should_run = False
        QTimer.singleShot(1000, self.close)
