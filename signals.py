from PyQt5.QtCore import QObject, pyqtSignal

class Signals(QObject):
    load_standart_grid = pyqtSignal()

    def __init__(self, parent: QObject | None = ...) -> None:
        super().__init__(parent)


SIGNALS = Signals()