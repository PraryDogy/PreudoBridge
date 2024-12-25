import re
from typing import Literal

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QContextMenuEvent, QMouseEvent, QWheelEvent
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import QFrame, QLineEdit, QMenu, QSlider, QWidget

from cfg import Static
from database import ColumnNames, Dynamic, OrderItem
from utils import Utils


class BaseMethods:
    def order_(self, *args, **kwargs):
        raise Exception("Переопредели метод sort_grid")

    def filter_(self, *args, **kwargs):
        raise Exception("Переопредели метод filter_grid")

    def resize_(self, *args, **kwargs):
        raise Exception("Переопредели метод resize_grid")
    
    def rearrange(self, *args, **kwargs):
        raise Exception("Переопредели метод rearrange")


class UMenu(QMenu):

    def mouseReleaseEvent(self, a0):
        if a0.button() == Qt.MouseButton.RightButton:
            a0.ignore()
        else:
            super().mouseReleaseEvent(a0)


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
                background-color: {Static.GRAY_SLIDER};
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
        self.setStyleSheet("padding-left: 2px; padding-right: 18px;")
        self.setFixedHeight(30)

        self.clear_btn = QSvgWidget(parent=self)
        self.clear_btn.load(Static.CLEAR_SVG)
        self.clear_btn.setFixedSize(14, 14)
        self.clear_btn.mouseReleaseEvent = lambda e: self.clear()
        self.clear_btn.enterEvent = (
            lambda e: self.setCursor(Qt.CursorShape.ArrowCursor)
        )
        self.clear_btn.leaveEvent = (
            lambda e: self.setCursor(Qt.CursorShape.IBeamCursor)
        )

        self.textChanged.connect(self.text_changed)
        self.clear_btn.hide()

    def text_changed(self):
        if self.text():
            self.clear_btn.show()
        else:
            self.clear_btn.hide()

    def clear_btn_vcenter(self):
        x = self.width() - self.clear_btn.width() - 6
        y = (self.height() - self.clear_btn.height()) // 2
        self.clear_btn.move(x, y)

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:

        # предотвращаем круговой импорт
        from ._actions import CopyText, TextCut, TextPaste, TextSelectAll

        menu = UMenu()

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


class UFrame(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("bar_top_btn")
        self.setStyleSheet(
            self.normal_style()
        )

    def normal_style(self):
        return f"""#bar_top_btn {{
                        background: transparent;
                }}"""

    def solid_style(self):
        return f"""#bar_top_btn {{
                        background: {Static.GRAY_UP_BTN}; 
                        border-radius: 5px;
                }}"""

    def enterEvent(self, a0):
        self.setStyleSheet(
            self.solid_style()
        )

    def leaveEvent(self, a0):

        self.setStyleSheet(
            self.normal_style()
        )


class Sort:
    # Как работает сортировка:
    # пользователь выбрал сортировку "по размеру"
    # в Dynamic в аттрибут "sort" записывается значение "size"
    # CACHE колонка имеет имя "size"
    # OrderItem имеет аттрибут "size"
    # на основе аттрибута "size" происходит сортировка списка из OrderItem

    @classmethod
    def sort_order_items(cls, order_items: list[OrderItem]) -> list[OrderItem]:
        
        attr = Dynamic.sort
        rev = Dynamic.rev

        if attr == ColumnNames.NAME:

            # сортировка по имени:
            # создаем список элементов, у которых в начале числовые символы
            # и список элементов, у которых в начале нечисловые символы
            # сортируем каждый список по отдельности
            # возвращаем объединенный список

            nums: list[OrderItem] = []
            abc: list[OrderItem] = []

            for i in order_items:

                if i.name[0].isdigit():
                    nums.append(i)

                else:
                    abc.append(i)

            # сортировка по числам в начале OrderItem.name
            key_num = lambda order_item: cls.get_nums(order_item)

            # сортировка по OrderItem.name
            key_abc = lambda order_item: getattr(order_item, attr)

            nums.sort(key=key_num, reverse=rev)
            abc.sort(key=key_abc, reverse=rev)

            return [*nums, *abc]

        else:

            key = lambda order_item: getattr(order_item, attr)
            order_items.sort(key=key, reverse=rev)
            return order_items

    # извлекаем начальные числа из order_item.name
    # по которым будет сортировка, например: "123 Te99st33" > 123
    # re.match ищет числа до первого нечислового символа
    @classmethod
    def get_nums(cls, order_item: OrderItem):

        return int(
            re.match(r'^\d+', order_item.name).group()
        )