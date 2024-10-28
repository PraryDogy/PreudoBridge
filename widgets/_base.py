from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QMouseEvent, QWheelEvent
from PyQt5.QtWidgets import QScrollArea, QSlider, QTableView, QWidget

from cfg import GRAY


class BaseMethods:
    def order_(self, *args, **kwargs):
        raise Exception("Переопредели метод sort_grid")

    def filter_(self, *args, **kwargs):
        raise Exception("Переопредели метод filter_grid")

    def resize_(self, *args, **kwargs):
        raise Exception("Переопредели метод resize_grid")
    
    def rearrange(self, *args, **kwargs):
        raise Exception("Переопредели метод rearrange")


class BaseGrid(QScrollArea, BaseMethods):
    def __init__(self):
        QScrollArea.__init__(self)
        BaseMethods.__init__(self)


class BaseTableView(QTableView, BaseMethods):
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
                background-color: {GRAY};
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


class WinBase(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowModality(Qt.WindowModality.ApplicationModal)


class WinMinMax(WinBase):
    def __init__(self):
        super().__init__()
        fl = Qt.WindowType.Window | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowCloseButtonHint
        self.setWindowFlags(fl)
