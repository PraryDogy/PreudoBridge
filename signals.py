from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QWidget


class Signals(QObject):
    load_standart_grid = pyqtSignal(dict)
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
    bar_bottom_cmd = pyqtSignal(dict)

    move_slider = pyqtSignal(int)

    def load_standart_grid_cmd(self, path: str, prev_path: str | None):

        data = {
            "path": path,
            "prev_path": prev_path
        }

        self.load_standart_grid.emit(data)


class SignalsApp:
    instance: Signals = None

    @classmethod
    def init(cls):
        cls.instance = Signals()

    @classmethod
    def disconnect_grid(cls) -> bool:

        recon = (
            SignalsApp.instance.resize_grid,
            SignalsApp.instance.sort_grid,
            SignalsApp.instance.filter_grid,
            SignalsApp.instance.move_to_wid
            )

        for sig in recon:
            try:
                sig.disconnect()
            except TypeError:
                return False
            
        return True