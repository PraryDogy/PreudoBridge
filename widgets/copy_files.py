import os
import shutil

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import (QApplication, QDialog, QLabel, QProgressBar,
                             QPushButton, QVBoxLayout, QHBoxLayout)

from cfg import Static


class FileMoverThread(QThread):
    progress = pyqtSignal(int)  # Сигнал для обновления прогресса
    finished = pyqtSignal()    # Сигнал, что работа завершена

    def __init__(self, files_and_folders, destination):
        super().__init__()
        self.files_and_folders = files_and_folders
        self.destination = destination

    def run(self):
        total_items = len(self.files_and_folders)
        for index, item in enumerate(self.files_and_folders):
            self.move_item(item, self.destination)
            progress_percent = int(((index + 1) / total_items) * 100)
            self.progress.emit(progress_percent)

        from time import sleep
        sleep(3)
        self.finished.emit()

    @staticmethod
    def move_item(item, destination):
        # Если это файл
        if os.path.isfile(item):
            shutil.move(item, os.path.join(destination, os.path.basename(item)))
        # Если это папка
        elif os.path.isdir(item):
            shutil.move(item, os.path.join(destination, os.path.basename(item)))


class ProgressDialog(QDialog):
    def __init__(self, files_and_folders: list, destination: str, title: str):
        super().__init__()

        self.setWindowTitle(title)
        self.setFixedSize(300, 100)
        self.setWindowFlag(Qt.WindowType.CustomizeWindowHint, True)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)

        h_lay = QHBoxLayout(self)
        self.setLayout(h_lay)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 0)
        h_lay.addWidget(self.progress_bar)

        self.cancel_button = QSvgWidget()
        self.cancel_button.load(Static.CLEAR_SVG)
        self.cancel_button.setFixedSize(16, 16)
        self.cancel_button.mouseReleaseEvent = self.close_thread
        h_lay.addWidget(self.cancel_button)

        self.task_ = FileMoverThread(files_and_folders, destination)
        self.task_.progress.connect(self.update_progress)
        self.task_.finished.connect(self.on_finished)

        # Подключаем кнопку "Отмена"
        # self.cancel_button.clicked.connect(self.close_thread)

        # Запускаем поток
        # self.task_.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def on_finished(self):
        ...

    def close_thread(self, *args):
        if self.task_.isRunning():
            self.task_.terminate()
        self.close()
