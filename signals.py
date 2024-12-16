from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QWidget
from typing import Literal

class Signals(QObject):
    load_standart_grid = pyqtSignal(str)
    load_search_grid = pyqtSignal(str)

    # эти сигналы переназначаются заново, не забудь отключить прежде
    resize_grid = pyqtSignal()
    sort_grid = pyqtSignal()
    filter_grid = pyqtSignal()
    move_to_wid = pyqtSignal(QWidget)
    # end

    fav_cmd = pyqtSignal(dict)
    set_search_title = pyqtSignal(str)
    move_to_wid_delayed = pyqtSignal(str)
    open_path = pyqtSignal(str)
    new_history_item = pyqtSignal(str)
    _path_labels_cmd = pyqtSignal(dict)

    move_slider = pyqtSignal(int)


class SignalsApp:
    all_: Signals = None

    @classmethod
    def init(cls):
        cls.all_ = Signals()

    @classmethod
    def disconnect_grid(cls) -> bool:

        recon = (
            SignalsApp.all_.resize_grid,
            SignalsApp.all_.sort_grid,
            SignalsApp.all_.filter_grid,
            SignalsApp.all_.move_to_wid
            )

        for sig in recon:
            try:
                sig.disconnect()
            except TypeError:
                return False
            
        return True