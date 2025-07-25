import os
import re

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import (QContextMenuEvent, QCursor, QMouseEvent, QPixmap,
                         QWheelEvent)
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import (QFrame, QLabel, QLineEdit, QMenu, QScrollArea,
                             QSlider, QTableView, QTextEdit, QWidget)

from cfg import Static


class UMethods:
    """
    Базовые методы для GridStandart, GridSearch и GridList
    """
    def sort_thumbs(self, *args, **kwargs):
        raise Exception("Переопредели метод sort_grid")

    def filter_thumbs(self, *args, **kwargs):
        raise Exception("Переопредели метод filter_grid")

    def resize_thumbs(self, *args, **kwargs):
        raise Exception("Переопредели метод resize_grid")
    
    def rearrange_thumbs(self, *args, **kwargs):
        raise Exception("Переопредели метод rearrange")


class UScrollArea(QScrollArea, UMethods):
    """
    Виджет с базовыми сигналами. Сигналы должны совпадать с UTableView
    """
    new_history_item = pyqtSignal(str)
    path_bar_update = pyqtSignal(str)
    add_fav = pyqtSignal(str)
    del_fav = pyqtSignal(str)
    load_st_grid = pyqtSignal()
    move_slider = pyqtSignal(int)
    change_view = pyqtSignal(int)
    open_in_new_win = pyqtSignal(str)
    level_up = pyqtSignal()
    sort_menu_update = pyqtSignal()
    total_count_update = pyqtSignal(int)
    finished_ = pyqtSignal()

    def __init__(self):
        """
        Безрамочный стиль
        """
        super().__init__()
        self.setStyleSheet("QScrollArea { border: none; }")


class UTableView(QTableView, UMethods):
    """
    Виджет с базовыми сигналами. Сигналы должны совпадать с UScrollArea
    """
    new_history_item = pyqtSignal(str)
    path_bar_update = pyqtSignal(str)
    add_fav = pyqtSignal(str)
    del_fav = pyqtSignal(str)
    load_st_grid = pyqtSignal()
    move_slider = pyqtSignal(int)
    change_view = pyqtSignal(int)
    open_in_new_win = pyqtSignal(str)
    level_up = pyqtSignal()
    sort_menu_update = pyqtSignal()
    total_count_update = pyqtSignal(int)
    finished_ = pyqtSignal()


class UMenu(QMenu):
    def __init__(self, title: str = None, parent: QWidget = None):
        super().__init__(title, parent)
        """
        Контекстное меню:
        - отключен правый клик
        - show_: открывает контекстное меню по месту клика
        """

    def show_(self):
        self.exec_(QCursor.pos())

    def mouseReleaseEvent(self, a0):
        if a0.button() == Qt.MouseButton.RightButton:
            a0.ignore()
        else:
            super().mouseReleaseEvent(a0)


class USlider(QSlider):
    def __init__(self, orientation: Qt.Orientation, minimum: int, maximum: int):
        """
        Базовый слайдер с пользовательским стилем   
        Игнорирует правые клики     
        Игнорирует колесико мыши
        """
        super().__init__()
        self.setOrientation(orientation)
        self.setMinimum(minimum)
        self.setMaximum(maximum)

        st = f"""
            QSlider {{
                height: 15px;
            }}
            QSlider::groove:horizontal {{
                border-radius: 1px;
                margin: 0;
                height: 3px;
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


class USvgSqareWidget(QSvgWidget):
    def __init__(self, src: str, size: int):
        """
        Квадратный Svg виджет
        """
        super().__init__()
        self.setStyleSheet(f"""background-color: transparent;""")
        self.renderer().setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self.setFixedSize(size, size)
        if src:
            self.load(src)


class ULineEdit(QLineEdit):
    def __init__(self):
        """
        - Виджет однострочного ввода текста   
        - Пользовательское контекстное меню: вырезать, копировать, вставить, выделить все     
        - Кнопка "стереть" справа внутри поля ввода текста    
        - Необходимо установить фиксированную ширину виджета для корректного
        позиционирования кнопки "стереть"
        """
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
        """
        Отлов сигнала textChanged
        """
        if self.text():
            self.move_clear_btn()
            self.clear_btn.show()
        else:
            self.clear_btn.hide()

    def move_clear_btn(self):
        """
        Перемещает кнопку "стереть" вертикально по центру и к правой стороне
        """
        x = self.width() - self.clear_btn.width() - 6
        y = (self.height() - self.clear_btn.height()) // 2
        self.clear_btn.move(x, y)

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:
        # Предотвращаем круговой импорт, т.к. в actions.py есть импорт UMenu
        from .actions import CopyText, CutText, PasteText, TextSelectAll

        menu = UMenu()

        cut_a = CutText(menu, self)
        menu.addAction(cut_a)

        copy_a = CopyText(menu, self)
        menu.addAction(copy_a)

        paste_a = PasteText(menu, self)
        menu.addAction(paste_a)

        menu.addSeparator()

        select_all_a = TextSelectAll(menu, self)
        menu.addAction(select_all_a)

        menu.show_()


class UTextEdit(QTextEdit):
    def __init__(self):
        """
        - Виджет многострочного ввода текста  
        - Пользовательское контекстное меню: вырезать, копировать, вставить, выделить все     
        - Допускается только простой текст, форматирование текста при вставке
        будет удалено
        """
        super().__init__()
        self.setAcceptRichText(False)

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:
        # Предотвращаем круговой импорт, т.к. в actions.py есть импорт UMenu
        from .actions import CopyText, CutText, PasteText, TextSelectAll

        menu = UMenu()

        cut_a = CutText(menu, self)
        menu.addAction(cut_a)

        copy_a = CopyText(menu, self)
        menu.addAction(copy_a)

        paste_a = PasteText(menu, self)
        menu.addAction(paste_a)

        menu.addSeparator()

        select_all_a = TextSelectAll(menu, self)
        menu.addAction(select_all_a)

        menu.show_()


class USep(QFrame):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background: rgba(0, 0, 0, 0.2)")
        self.setFixedHeight(1)


class UFrame(QFrame):
    object_name = "bar_top_btn"

    def __init__(self):
        """
        Стандартный QFrame с пользовательским стилем:   
        При наведении курсора мыши на виджет, он принимает выделенный стиль
        """
        super().__init__()
        self.setObjectName(UFrame.object_name)
        self.setStyleSheet(self.normal_style())

    def normal_style(self):
        return f"""#{UFrame.object_name} {{
                        background: transparent;
                        padding-left: 2px;
                        padding-right: 2px;
                }}"""

    def solid_style(self):
        return f"""#{UFrame.object_name} {{
                        background: {Static.GRAY_GLOBAL}; 
                        border-radius: 7px;
                        padding-left: 2px;
                        padding-right: 2px;
                }}"""

    def enterEvent(self, a0):
        self.setStyleSheet(self.solid_style())

    def leaveEvent(self, a0):
        self.setStyleSheet(self.normal_style())


class WinBase(QWidget):
    wins: list["WinBase"] = []

    def __init__(self):
        """
        Окно QWidget с функцией "center", которая выравнивает окно по центру
        относительно родительского.
        """
        super().__init__()
        self.add_to_list()
        # self.setWindowModality(Qt.WindowModality.ApplicationModal)

    def add_to_list(self):
        WinBase.wins.append(self)

    def remove_from_list(self):
        WinBase.wins.remove(self)

    def center(self, parent: QWidget):
        """
        Центрирует текущее окно относительно родительского окна.
        """
        parent.raise_()
        geo = self.geometry()
        geo.moveCenter(parent.geometry().center())
        self.setGeometry(geo)

    def set_modality(self):
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

    def deleteLater(self):
        self.remove_from_list()
        return super().deleteLater()
    
    def closeEvent(self, a0):
        self.remove_from_list()
        return super().closeEvent(a0)


class MinMaxDisabledWin(WinBase):
    def __init__(self):
        """
        Окно без кнопок свернуть и развернуть.  
        Оставлена только кнопка закрытия.
        """
        super().__init__()
        fl = Qt.WindowType.Window | Qt.WindowType.CustomizeWindowHint
        fl = fl  | Qt.WindowType.WindowCloseButtonHint
        self.setWindowFlags(fl)


class LoadingWid(QLabel):
    text_ = "Загрузка"
    def __init__(self, parent: QWidget):
        super().__init__(LoadingWid.text_, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            f"""
                background: {Static.GRAY_GLOBAL};
                border-radius: 4px;
            """
        )

    def center(self, parent: QWidget):
        geo = self.geometry()
        geo.moveCenter(parent.geometry().center())
        self.setGeometry(geo)