from typing import Any
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QWidget

class Signals(QObject):
    load_standart_grid = pyqtSignal(str)
    load_search_grid = pyqtSignal(str)

    # эти сигналы переназначаются заново, не забудь отключить прежде
    resize_grid = pyqtSignal()
    sort_grid = pyqtSignal()
    filter_grid = pyqtSignal()
    move_to_wid = pyqtSignal(QWidget)

    add_fav = pyqtSignal(str)
    del_fav = pyqtSignal(str)
    search_finished = pyqtSignal(str)
    show_in_folder = pyqtSignal(str)
    progressbar_value = pyqtSignal(object)
    open_path = pyqtSignal(str)
    new_history = pyqtSignal(str)
    create_path_labels = pyqtSignal(object, object)

    def __init__(self) -> None:
        super().__init__()


class SignalsApp:
    all: Signals = None

    @classmethod
    def init(cls):
        cls.all = Signals()
