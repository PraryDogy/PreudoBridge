import os
import re

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import (QColor, QContextMenuEvent, QCursor, QMouseEvent,
                         QPalette, QWheelEvent)
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import (QApplication, QFrame, QGraphicsDropShadowEffect,
                             QHBoxLayout, QLabel, QLineEdit, QMenu,
                             QScrollArea, QSlider, QTextEdit,
                             QWidget)

from cfg import Static


class UScrollArea(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("QScrollArea { border: none; }")


class UMenu(QMenu):
    def __init__(self, title: str = None, parent: QWidget = None):
        super().__init__(title, parent)
        """
        Контекстное меню:
        - отключен правый клик
        - show_: открывает контекстное меню по месту клика
        """
        palette = QApplication.palette()
        text_color = palette.color(QPalette.WindowText).name().lower()

        color_data = {
            "#000000": "#8a8a8a",
            "#ffffff": "#5A5A5A",
        }

        sep_color = color_data.get(text_color)  # дефолт если нет ключа

        self.setStyleSheet(f"""
            QMenu::separator {{
                height: 1px;
                background: {sep_color};
                margin: 4px 10px;
            }}
        """)

    def show_under_cursor(self):
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

    def wheelEvent(self, e: QWheelEvent | None) -> None:
        e.ignore()

    def mousePressEvent(self, ev: QMouseEvent) -> None:
        if ev.button() != Qt.LeftButton:
            ev.ignore()
            return

        ratio = ev.x() / self.width()
        value = self.minimum() + round(ratio * (self.maximum() - self.minimum()))
        self.setValue(value)
        ev.accept()
        return super().mousePressEvent(ev)


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
        self.clear_btn.load(Static.INTERNAL_ICONS.get("clear.svg"))
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
        return
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

        menu.show_under_cursor()


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

        menu.show_under_cursor()


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
        try:
            WinBase.wins.remove(self)
        except ValueError:
            ...

    def center(self, parent: QWidget):
        """
        Центрирует текущее окно относительно родительского окна.
        """
        parent.raise_()
        geo = self.geometry()
        geo.moveCenter(parent.geometry().center())
        self.setGeometry(geo)

    def set_modality(self):
        """
        Устанавливает модальность окна на уровень всего приложения.
        При этом окно блокирует взаимодействие с другими окнами приложения
        и всегда остаётся поверх них до своего закрытия.
        """
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


class NotifyWid(QFrame):
    ms = 1500

    def __init__(self, parent: QWidget, text: str, svg_path: str):
        super().__init__(parent=parent)

        self.setObjectName("notifyWidget")
        self.setStyleSheet(
            f"""
            #notifyWidget {{
                background: {Static.BLUE_GLOBAL};
                border-radius: 10px;
                font-size: 16px;
            }}
            #notifyWidget QLabel {{
                color: white;
            }}
            """
        )

        # иконка
        self.icon = QSvgWidget(svg_path, self)
        self.icon.setFixedSize(20, 20)

        # текст
        self.label = QLabel(text, self)
        self.label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

        # лейаут
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        layout.addWidget(self.icon)
        layout.addWidget(self.label)

        # тень
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(12)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 160))
        self.setGraphicsEffect(shadow)

        self.adjustSize()

    def _show(self):
        self.adjustSize()
        pw, ph = self.parent().width(), self.parent().height()
        x = (pw - self.width()) // 2
        y = 10
        self.move(x, y)
        self.show()
        QTimer.singleShot(self.ms, self._close)

    def _close(self):
        self.setGraphicsEffect(None)
        self.hide()
        self.deleteLater()
