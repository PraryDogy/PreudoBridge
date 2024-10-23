from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QMouseEvent, QWheelEvent
from PyQt5.QtWidgets import QScrollArea, QSlider, QTableView

from signals import SIGNALS


class BaseMethods:
    def rearrange_grid(self, *args, **kwargs):
        raise Exception("Переопредели метод resize")

    def sort_grid(self, *args, **kwargs):
        raise Exception("Переопредели метод sort_grid")

    def move_to_wid(self, *args, **kwargs):
        raise Exception("Переопредели метод move_to_wid")

    def filter_grid(self, *args, **kwargs):
        raise Exception("Переопредели метод filter_grid")

    def resize_grid(self, *args, **kwargs):
        raise Exception("Переопредели метод resize_grid")


class BaseGrid(QScrollArea, BaseMethods):
    add_fav = pyqtSignal(str)
    del_fav = pyqtSignal(str)
    progressbar_start = pyqtSignal(int)
    progressbar_value = pyqtSignal(int)
    show_in_folder = pyqtSignal(str)

    def __init__(self):
        QScrollArea.__init__(self)
        BaseMethods.__init__(self)


class BaseTableView(QTableView, BaseMethods):
    add_fav = pyqtSignal(str)
    del_fav = pyqtSignal(str)
    progressbar_start = pyqtSignal(int)
    progressbar_value = pyqtSignal(int)
    show_in_folder = pyqtSignal(str)
    level_up = pyqtSignal()

    def __init__(self):
        QTableView.__init__(self)
        BaseMethods.__init__(self)


class BaseSlider(QSlider):
    _clicked = pyqtSignal()

    def __init__(self, orientation: Qt.Orientation, minimum: int, maximum: int):
        super().__init__(orientation=orientation, minimum=minimum, maximum=maximum)

        st = f"""
            QSlider::groove:horizontal {{
                border-radius: 1px;
                height: 3px;
                margin: 0px;
                background-color: rgba(111, 111, 111, 0.5);
            }}
            QSlider::handle:horizontal {{
                background-color: rgba(199, 199, 199, 1);
                height: 10px;
                width: 10px;
                border-radius: 5px;
                margin: -4px 0;
                padding: -4px 0px;
            }}
            """

        self.setStyleSheet(st)

    def mouseReleaseEvent(self, ev: QMouseEvent | None) -> None:
        if ev.button() == Qt.MouseButton.LeftButton:
            super().mouseReleaseEvent(ev)
        else:
            ev.ignore()

    def wheelEvent(self, e: QWheelEvent | None) -> None:
        e.ignore()
