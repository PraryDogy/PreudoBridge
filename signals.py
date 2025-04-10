from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QWidget


class Signals(QObject):
    filter_grid = pyqtSignal()  
    load_any_grid = pyqtSignal(tuple)  
    load_search_grid = pyqtSignal(str)  
    move_slider = pyqtSignal(int)  
    move_to_wid = pyqtSignal(QWidget)  
    open_path = pyqtSignal(str)
    rearrange_grid = pyqtSignal() 
    resize_grid = pyqtSignal()  


class SignalsApp:
    """
    bar_bottom_cmd: (path for display in the bottom bar | None, total grid widgets count | None)    
    fav_cmd: ("select" or "add" or "del", path to dir)     
    filter_grid: None  
    load_any_grid: (path to dir for grid, path: widget in the grid will be selectet if its path matches | None)   
    load_search_grid: str (search text)  
    load_standart_grid: (path to dir for grid, path: widget in the grid will be selectet if its path matches | None)   
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
    def remove_grid_connections(cls) -> bool:

        recon = (
            SignalsApp.instance.rearrange_grid,
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