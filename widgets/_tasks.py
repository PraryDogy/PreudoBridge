from PyQt5.QtCore import QObject, pyqtSignal

from cfg import Static
from system.path_finder import PathFinder as PathFinder_

from ._base_widgets import URunnable


class PathFinderSignals(QObject):
    finished_ = pyqtSignal(str)


class PathFinder(URunnable):
    volumes = "/Volumes"

    def __init__(self, path: str):
        super().__init__()
        self.signals = PathFinderSignals()
        self.path = path

    def task(self):
        self.path_finder_ = PathFinder_(self.path)
        result = self.path_finder_.get_result()
        if result is None:
            result = ""
        self.signals.finished_.emit(result)
