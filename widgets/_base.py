from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QContextMenuEvent, QMouseEvent, QWheelEvent
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import QLineEdit, QMenu, QSlider, QWidget

from cfg import GRAY_SLIDER
from utils import Utils

from ._actions import CopyText, TextCut, TextPaste, TextSelectAll
from typing import Literal

class BaseMethods:
    def order_(self, *args, **kwargs):
        raise Exception("Переопредели метод sort_grid")

    def filter_(self, *args, **kwargs):
        raise Exception("Переопредели метод filter_grid")

    def resize_(self, *args, **kwargs):
        raise Exception("Переопредели метод resize_grid")
    
    def rearrange(self, *args, **kwargs):
        raise Exception("Переопредели метод rearrange")


class USlider(QSlider):
    _clicked = pyqtSignal()

    def __init__(self, orientation: Qt.Orientation, minimum: int, maximum: int):
        super().__init__(orientation=orientation, minimum=minimum, maximum=maximum)
        st = f"""
            QSlider {{
                height: 15px;
            }}
            QSlider::groove:horizontal {{
                border-radius: 1px;
                margin: 0;
                height: 3px;
                background-color: {GRAY_SLIDER};
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



class USvgWidget(QSvgWidget):
    def __init__(self, **kwargs: Literal["src", "size"]):
        """src, size"""

        super().__init__()
        self.setStyleSheet(f"""background-color: transparent;""")
        self.renderer().setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        if kwargs.get("src"):
            self.load(kwargs.get("src"))
        if kwargs.get("size"):
            self.setFixedSize(kwargs.get("size"), kwargs.get("size"))


class ULineEdit(QLineEdit):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("padding-left: 2px; padding-right: 2px;")

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:
        menu = QMenu()

        cut_a = TextCut(menu, self)
        menu.addAction(cut_a)

        copy_a = CopyText(menu, self)
        menu.addAction(copy_a)

        paste_a = TextPaste(menu, self)
        menu.addAction(paste_a)

        menu.addSeparator()

        select_all_a = TextSelectAll(menu, self)
        menu.addAction(select_all_a)

        menu.exec_(self.mapToGlobal(a0.pos()))


class WinBase(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowModality(Qt.WindowModality.ApplicationModal)


class WinMinMax(WinBase):
    def __init__(self):
        super().__init__()
        fl = Qt.WindowType.Window | Qt.WindowType.CustomizeWindowHint
        fl = fl  | Qt.WindowType.WindowCloseButtonHint
        self.setWindowFlags(fl)


class OpenWin:

    @classmethod
    def info(cls, parent: QWidget, src: str):
        from .win_info import WinInfo
        cls.win = WinInfo(src)
        Utils.center_win(parent, cls.win)
        cls.win.show()

    @classmethod
    def view(cls, parent: QWidget, src: str):
        from .win_img_view import WinImgView
        cls.win = WinImgView(src)
        Utils.center_win(parent, cls.win)
        cls.win.show()