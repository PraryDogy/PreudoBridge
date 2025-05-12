from PyQt5.QtCore import QObject, pyqtSignal

from utils import PathFinder

from ._base_items import URunnable


class PathFinderSignals(QObject):
    finished_ = pyqtSignal(str)


class PathFinderTask(URunnable):
    def __init__(self, path: str):
        super().__init__()
        self.signals = PathFinderSignals()
        self.path = path

    def task(self):
        path_finder = PathFinder()
        result = path_finder.get_result(self.path)
        self.signals.finished_.emit(result)