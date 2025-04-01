from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QWidget


class Signals(QObject):
    load_any_grid = pyqtSignal(dict)
    load_standart_grid = pyqtSignal(dict)
    load_search_grid = pyqtSignal(str)

    # эти сигналы переназначаются заново, не забудь отключить прежде
    resize_grid = pyqtSignal()
    filter_grid = pyqtSignal()
    move_to_wid = pyqtSignal(QWidget)
    # end

    fav_cmd = pyqtSignal(dict)
    set_search_title = pyqtSignal(str)
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
    """
    load_any_grid: dict {"path": str, "prev_path": str}
    load_standart_grid: dict {"path": str, "prev_path": str}
    load_search_grid: str (search text)
    resize_grid: None
    filter_grid: None
    move_to_wid: QWidget (widgets > _grid.py > Thumb)
    fav_cmd: dict {"cmd": "select" or "add" or "del", "src": str (path)}
    set_search_title: str (text)
    open_path: str (path)
    new_history_item: str (path)
    bar_bottom_cmd: dict {"src": str (path), "total": int}
    move_slider: int
    """

    instance: Signals = None

    @classmethod
    def init(cls):
        cls.instance = Signals()

    @classmethod
    def disconnect_grid(cls) -> bool:

        recon = (
            SignalsApp.instance.resize_grid,
            SignalsApp.instance.filter_grid,
            SignalsApp.instance.move_to_wid
            )

        for sig in recon:
            try:
                sig.disconnect()
            except TypeError:
                return False
            
        return True