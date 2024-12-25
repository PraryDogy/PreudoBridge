import os
import shutil

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import QHBoxLayout, QProgressBar, QWidget

from cfg import JsonData, Static
from signals import SignalsApp

# URUNNABLE # URUNNABLE # URUNNABLE # URUNNABLE # URUNNABLE # URUNNABLE # URUNNABLE 


class FileMoverThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal()

    def __init__(self, items: list, dest: str):

        super().__init__()

        self.items = items
        self.dest = dest

    def run(self):

        total_items = len(self.items)

        for index, item in enumerate(self.items):

            try:
                self.move_item(item=item, destination=self.dest)
            except (shutil.SameFileError, IsADirectoryError):
                 ...

            progress_percent = int(((index + 1) / total_items) * 100)
            self.progress.emit(progress_percent)

        self.finished.emit()

    @staticmethod
    def move_item(item, destination):

        if os.path.isfile(item):
            shutil.copy(
                item,
                os.path.join(destination, os.path.basename(item))
            )

        elif os.path.isdir(item):
            shutil.copy(
                item,
                os.path.join(destination, os.path.basename(item))
            )


class WinCopyFiles(QWidget):
    def __init__(self, items: list, dest: str, title: str):
        super().__init__()

        self.setWindowTitle(title)
        self.setFixedSize(300, 60)
        self.setWindowFlag(Qt.WindowType.CustomizeWindowHint, True)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)

        h_lay = QHBoxLayout(self)
        h_lay.setContentsMargins(15, 0, 15, 0)
        self.setLayout(h_lay)

        self.progress_bar = QProgressBar(self)
        h_lay.addWidget(self.progress_bar)

        self.cancel_button = QSvgWidget()
        self.cancel_button.load(Static.CLEAR_SVG)
        self.cancel_button.setFixedSize(16, 16)
        self.cancel_button.mouseReleaseEvent = self.close_thread
        h_lay.addWidget(self.cancel_button)


        if len(items) == 1 and os.path.isfile(items[0]):
                    self.progress_bar.setRange(0, 0)
        elif len(items) > 1:
            self.progress_bar.setMinimum(0)
            self.progress_bar.setMaximum(100)

        self.task_ = FileMoverThread(
            items=items,
            dest=dest
        )

        self.task_.progress.connect(self.update_progress)
        self.task_.finished.connect(self.on_finished)

        self.task_.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def on_finished(self):

        SignalsApp.instance.load_standart_grid_cmd(
             path=JsonData.root,
             prev_path=None
        )

        QTimer.singleShot(1000, self.close)

    def close_thread(self, *args):
        if self.task_.isRunning():
            self.task_.terminate()
        self.close()
