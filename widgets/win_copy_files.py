import os
import shutil

from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtWidgets import QLabel, QPushButton, QVBoxLayout

from cfg import Dynamic, JsonData, Static
from signals import SignalsApp
from utils import URunnable, UThreadPool

from ._base import WinMinMax

PREPARING_T = "Подготовка"
COPYING_T = "Копирую файлы"
CANCEL_T = "Отмена"


class WorderSignals(QObject):
    finished_ = pyqtSignal(list)  # Сигнал с результатами (новыми путями к файлам)
    progress = pyqtSignal(str)  # Сигнал для передачи статуса копирования


class FileCopyWorker(URunnable):
    def __init__(self):
        super().__init__()
        self.signals_ = WorderSignals()

    @URunnable.set_running_state
    def run(self):    
        new_paths = []
        total_files = len(Dynamic.files_to_copy)
        for index, object_path in enumerate(Dynamic.files_to_copy, start=1):

            if not self.should_run:
                self.signals_.finished_.emit(new_paths)
                return

            self.signals_.progress.emit(f"Копирую {index} из {total_files}")
            dest = os.path.join(JsonData.root, os.path.basename(object_path))

            if os.path.isfile(object_path):
                try:
                    shutil.copy2(object_path, dest)
                    new_paths.append(dest)
                except shutil.SameFileError as e:
                    print("files copy error", e)
            else:
                try:
                    shutil.copytree(object_path, dest)
                    new_paths.append(dest)
                except Exception as e:
                    print("files copy copytree error", e)
    
        self.signals_.finished_.emit(new_paths)


class WinCopyFiles(WinMinMax):
    finished_ = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)
        self.setFixedSize(250, 70)
        self.setWindowTitle(COPYING_T)

        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(10, 10, 10, 10)
        v_lay.setSpacing(10)
        self.setLayout(v_lay)

        self.copy_label = QLabel(text=PREPARING_T)
        v_lay.addWidget(self.copy_label)

        self.cancel_btn = QPushButton(text=CANCEL_T)
        self.cancel_btn.clicked.connect(self.cancel_cmd)
        self.cancel_btn.setFixedWidth(100)
        v_lay.addWidget(self.cancel_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.task_ = None

        if Dynamic.files_to_copy:
            self.task_ = FileCopyWorker()
            self.task_.signals_.progress.connect(self.set_progress)
            self.task_.signals_.finished_.connect(self.finished_task)
            UThreadPool.start(runnable=self.task_)

    def cancel_cmd(self, *args):
        if self.task_:
            self.task_.should_run = False
        self.close()

    def finished_task(self, new_paths: list[str]):
        SignalsApp.instance.load_standart_grid.emit(
            {"path": JsonData.root, "prev_path": new_paths}
        )

        del self.task_
        self.close()

    def set_progress(self, text: str):
        self.copy_label.setText(text)