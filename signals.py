from PyQt5.QtCore import QObject, pyqtSignal

class Signals(QObject):
    load_standart_grid = pyqtSignal(object)
    resize_grid = pyqtSignal(object)

    def __init__(self) -> None:
        super().__init__()


SIGNALS = Signals()