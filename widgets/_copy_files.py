import os
import shutil

from PyQt5.QtCore import QMimeData, QObject, Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import QVBoxLayout, QLabel, QPushButton, QWidget

from cfg import JsonData, Static
from signals import SignalsApp
from utils import URunnable, UThreadPool

COPY_TITLE = "Пожалуйста, подождите"
COPY_T = "копирую"
FROM_T = "из"
PREPARING_T = "Подготовка..."
CANCEL_T = "Отмена"
MAX_T = 35


class WorkerSignals(QObject):
    progress = pyqtSignal(str)
    finished_ = pyqtSignal(dict)


class CopyFilesThread(URunnable):

    def __init__(self, objects: dict[str, int], dest: str):

        super().__init__()

        self.signals_ = WorkerSignals()
        self.dest = os.sep + dest.strip(os.sep)
        self.counter = 0
        self.objects = objects
        self.new_objects: dict[str, int] = {}

    @URunnable.set_running_state
    def run(self):

        total = len(self.objects)

        for index, (src, rating) in enumerate(self.objects.items(), start=1):

            if not self.should_run:
                self.signals_.finished_.emit(self.counter)
                return

            try:
                path = os.path.join(self.dest, os.path.basename(src))
                new_src = shutil.copy(src, path)
                self.new_objects[new_src] = rating
                self.counter += 1

            except (shutil.SameFileError, IsADirectoryError):
                 ...

            filename = os.path.basename(src)
            t = f"{index} {FROM_T} {total}: {COPY_T} {filename}"

            if len(t) > MAX_T:
                t = t[:MAX_T] + "..."

            self.signals_.progress.emit(t)

        self.signals_.finished_.emit(self.new_objects)


class WinCopyFiles(QWidget):
    def __init__(self, objects: dict[str, int], dest: str):
        super().__init__()

        self.setWindowTitle(COPY_TITLE)
        self.setFixedSize(300, 70)

        self.dest = dest

        fl = Qt.WindowType.Window | Qt.WindowType.CustomizeWindowHint
        fl = fl  | Qt.WindowType.WindowCloseButtonHint
        self.setWindowFlags(fl)

        h_lay = QVBoxLayout(self)
        h_lay.setContentsMargins(15, 10, 15, 10)
        self.setLayout(h_lay)

        self.progress_label = QLabel(text=PREPARING_T)
        h_lay.addWidget(self.progress_label)

        self.cancel_button = QPushButton(text=CANCEL_T)
        self.cancel_button.setFixedWidth(100)
        self.cancel_button.clicked.connect(self.close_thread)
        h_lay.addWidget(self.cancel_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self.task_ = CopyFilesThread(objects=objects,dest=dest)
        self.task_.signals_.progress.connect(self.update_progress)
        self.task_.signals_.finished_.connect(self.on_finished)
        UThreadPool.start(runnable=self.task_)

    def update_progress(self, text: str):
        self.progress_label.setText(text)

    def on_finished(self, objects: dict[str, int]):

        if len(objects) > 0 and JsonData.root == self.dest:

            SignalsApp.instance.load_standart_grid_cmd(
                path=JsonData.root,
                prev_path=None
            )

        QTimer.singleShot(200, self.close)

    def close_thread(self, *args):
        self.task_.should_run = False
        QTimer.singleShot(200, self.close)

    def custom_show(self):

        if self.task_.is_running:
            self.show()