import subprocess

from PyQt5.QtCore import QObject, QRunnable, pyqtSignal

from cfg import JsonData
from signals import SignalsApp


class WorkerSignals(QObject):
    finished_ = pyqtSignal()


class DeleteFilesTask(QRunnable):
    def __init__(self, urls: list[str]):
        super().__init__()
        self.urls = urls

    def run(self):
        subprocess.run(["rm", "-rf"] + self.urls, check=True)
        SignalsApp.instance.load_standart_grid_cmd(
            path=JsonData.root,
            prev_path=None
        )