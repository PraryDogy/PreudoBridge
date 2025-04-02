from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QWidget


class Signals(QObject):
    bar_bottom_cmd = pyqtSignal(tuple)  
    fav_cmd = pyqtSignal(dict)  
    filter_grid = pyqtSignal()  
    load_any_grid = pyqtSignal(dict)  
    load_search_grid = pyqtSignal(str)  
    load_standart_grid = pyqtSignal(dict)  
    move_slider = pyqtSignal(int)  
    move_to_wid = pyqtSignal(QWidget)  
    new_history_item = pyqtSignal(str)  
    open_path = pyqtSignal(str)  
    resize_grid = pyqtSignal()  
    set_search_title = pyqtSignal(str)  


class SignalsApp:
    """
    bar_bottom_cmd: (str(path) | None, int(total grid widgets count) | None)
    fav_cmd: dict {"cmd": "select" or "add" or "del", "src": str (path)}  
    filter_grid: None  
    load_any_grid: dict {"path": str, "prev_path": str or None}  
    load_search_grid: str (search text)  
    load_standart_grid: dict {"path": str, "prev_path": str or None}  
    move_slider: int  
    move_to_wid: QWidget (widgets > _grid.py > Thumb)  
    new_history_item: str (path)  
    open_path: str (path)  
    resize_grid: None  
    set_search_title: str (text)  
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