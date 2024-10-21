from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QScrollArea, QTableView


class BaseMethods:
    def resize_grid(self, *args, **kwargs):
        raise Exception("Переопредели метод resize")

    def sort_grid(self, *args, **kwargs):
        raise Exception("Переопредели метод sort_grid")

    def move_to_wid(self, *args, **kwargs):
        raise Exception("Переопредели метод move_to_wid")

    def filter_grid(self, *args, **kwargs):
        raise Exception("Переопредели метод filter_grid")


class BaseGrid(QScrollArea, BaseMethods):
    add_fav = pyqtSignal(str)
    del_fav = pyqtSignal(str)
    clicked_folder = pyqtSignal(str)
    progressbar_start = pyqtSignal(int)
    progressbar_value = pyqtSignal(int)
    show_in_folder = pyqtSignal(str)

    def __init__(self):
        QScrollArea.__init__(self)
        BaseMethods.__init__(self)


class BaseTableView(QTableView, BaseMethods):
    add_fav = pyqtSignal(str)
    del_fav = pyqtSignal(str)
    clicked_folder = pyqtSignal(str)
    progressbar_start = pyqtSignal(int)
    progressbar_value = pyqtSignal(int)
    show_in_folder = pyqtSignal(str)

    def __init__(self):
        QTableView.__init__(self)
        BaseMethods.__init__(self)
