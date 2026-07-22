import os

from PyQt6.QtCore import QDir, QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (QAction, QColor, QContextMenuEvent, QCursor,
                         QFileSystemModel, QMouseEvent, QPalette, QTextCursor,
                         QWheelEvent)
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtWidgets import (QApplication, QFrame, QGraphicsDropShadowEffect,
                             QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                             QMainWindow, QMenu, QPushButton, QScrollArea,
                             QSlider, QTextEdit, QVBoxLayout, QWidget)

from cfg import Static
from system.items import ImgViewItem, NameUrlItem
from system.shared_utils import ImgUtils
from system.utils import Utils


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

        return
        self.setStyleSheet(f"""
            QMenu {{ 
                border-radius: 0px; 
            }}
        """)

    def show_under_mouse(self):
        self.exec(QCursor.pos())

    def add_action(self, action: QAction, callback: callable):
        action.triggered.connect(lambda: QTimer.singleShot(100, callback))
        self.addAction(action)

    def add_menu(self, menu: QMenu, callback: callable):
        menu.triggered.connect(callback)
        self.addMenu(menu)

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
        if ev.button() != Qt.MouseButton.LeftButton:
            ev.ignore()
            return

        ratio = ev.pos().x() / self.width()
        value = self.minimum() + round(ratio * (self.maximum() - self.minimum()))
        self.setValue(value)
        ev.accept()
        return super().mousePressEvent(ev)


class CopyPasteMenu(UMenu):
    def __init__(self, parent: QLineEdit | QTextEdit):
        super().__init__()
        self.parent_ = parent
        self.add_action(
            action=QAction("Вырезать", self),
            callback=lambda: self.cut_text()
        )
        self.add_action(
            action=QAction("Копировать", self),
            callback=lambda: self.copy_text()
        )
        if Utils.read_from_clipboard():
            self.add_action(
                action=QAction("Вставить", self),
                callback=lambda: self.paste_text()
            )
        self.addSeparator()
        self.add_action(
            action=QAction("Выделить все", self),
            callback=lambda: self.select_all()
        )

    def cut_text(self):
        if isinstance(self.parent_, QLineEdit):
            selection = self.get_selection()
            text = self.parent_.text().replace(selection, "")
            self.parent_.setText(text)
        elif isinstance(self.parent_, QTextEdit):
            self.wid.textCursor().removeSelectedText()
        Utils.write_to_clipboard(selection)

    def copy_text(self):
        Utils.write_to_clipboard(self.get_selection())

    def get_selection(self):
        if isinstance(self.parent_, QLineEdit):
            selection = self.parent_.selectedText()
        if isinstance(self.parent_, QTextEdit):
            selection = self.parent_.textCursor().selectedText()
        selection = selection.replace(Static.paragraph_symbol, "")
        selection = selection.replace(Static.line_feed_symbol, "")
        return selection

    def paste_text(self):
        text = Utils.read_from_clipboard()
        if isinstance(self.parent_, QLineEdit):
            new_text = self.parent_.text() + text
            self.parent_.setText(new_text)
        elif isinstance(self.parent_, QTextEdit):
            cursor = self.parent_.textCursor()
            cursor.insertText(text)
    
    def select_all(self):
        if isinstance(self.parent_, QLineEdit):
            self.parent_.selectAll()
        elif isinstance(self.parent_, QTextEdit):
            cursor = self.parent_.textCursor()
            cursor.select(QTextCursor.SelectionType.Document)
            self.parent_.setTextCursor(cursor)


class ULineEdit(QLineEdit):
    icon_path = os.path.join(Static.internal_images_dir, "clear.svg")
    icon_size = 14

    def __init__(self):
        super().__init__()
        self.setStyleSheet("padding-left: 2px; padding-right: 25px;")
        self.setFixedHeight(30)

        self.clear_btn = QSvgWidget(parent=self)
        self.clear_btn.load(self.icon_path)
        self.clear_btn.setFixedSize(self.icon_size, self.icon_size)
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
        x = self.width() - self.clear_btn.width() - 6
        y = (self.height() - self.clear_btn.height()) // 2
        self.clear_btn.move(x, y)

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:
        self.context_menu = CopyPasteMenu(parent=self)
        self.context_menu.show_under_mouse()


class UTextEdit(QTextEdit):
    def __init__(self):
        super().__init__()
        self.setAcceptRichText(False)

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:
        self.context_menu = CopyPasteMenu(parent=self)
        self.context_menu.show_under_mouse()


class USep(QFrame):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background: rgba(0, 0, 0, 0.2)")
        self.setFixedHeight(1)


class UFrame(QFrame):
    object_name = "bar_top_btn"

    def __init__(self):
        super().__init__()
        self.pressed = False
        self.setObjectName(UFrame.object_name)
        self.setStyleSheet(self.normal_style())

    def normal_style(self):
        return f"""#{self.object_name} {{
                        background: transparent;
                        padding-left: 2px;
                        padding-right: 2px;
                }}"""

    def solid_style(self):
        return f"""#{self.object_name} {{
                        background: rgba(128, 128, 128, 0.95); 
                        border-radius: 7px;
                        padding-left: 2px;
                        padding-right: 2px;
                }}"""

    def enterEvent(self, a0):
        self.setStyleSheet(self.solid_style())

    def leaveEvent(self, a0):
        if not self.pressed:
            self.setStyleSheet(self.normal_style())

    
class WinMixin:
    window_list: list[QWidget] = []

    def __init__(self):
        super().__init__()
        self.add_to_list()

    def add_to_list(self):
        self.window_list.append(self)

    def remove_from_list(self):
        if self in self.window_list:
            self.window_list.remove(self)

    def center(self: QWidget, parent: QWidget):
        parent.raise_()
        geo = self.geometry()
        geo.moveCenter(parent.geometry().center())
        self.setGeometry(geo)

    def set_always_on_top(self: QWidget):
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

    def set_close_only(self: QWidget):
        self.setWindowFlags(
            Qt.WindowType.CustomizeWindowHint |
            Qt.WindowType.WindowCloseButtonHint
        )

    def deleteLater(self):
        self.remove_from_list()
        return super().deleteLater()
    
    def closeEvent(self, a0):
        self.remove_from_list()
        return super().closeEvent(a0)


class UMainWindow(WinMixin, QMainWindow):
    def __init__(self):
        super().__init__()
        self.setCentralWidget(QWidget())


class UMainWidget(WinMixin, QWidget):
    def __init__(self):
        super().__init__()
        self.central_layout =  QVBoxLayout(self)


class NotifyWid(QFrame):
    ms = 1500

    def __init__(self, parent: QWidget, text: str, svg_path: str):
        super().__init__(parent=parent)

        self.setObjectName("notifyWidget")
        self.setStyleSheet(
            f"""
            #notifyWidget {{
                background: {Static.rgba_blue};
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
        self.label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

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


class BtnSmall(QPushButton):
    ww = 80
    def __init__(self, text: str):
        super().__init__(text)
        self.setFixedWidth(self.ww)
        self.setStyleSheet("""font-size: 11pt;""")


class HSep(QFrame):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background: rgba(128, 128, 128, 0.2)")
        self.setFixedHeight(1)


class UFileSystemModel(QFileSystemModel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        exts = [
            f"*{ext}"
            for ext in ImgUtils.ext_all
        ]
        self.setNameFilters(exts)
        self.setNameFilterDisables(False) 
        self.setFilter(
            QDir.Filter.Files | 
            QDir.Filter.AllDirs | 
            QDir.Filter.NoDotAndDotDot
        )


class BaseSignals(QObject):
    history_item = pyqtSignal(str)
    load_st_grid = pyqtSignal(str)
    new_main_win = pyqtSignal(str)
    new_fav = pyqtSignal(NameUrlItem)
    remove_fav = pyqtSignal(str)
    reveal_urls = pyqtSignal(list)
    copy_urls = pyqtSignal(list)
    copy_names = pyqtSignal(list)
    remove_urls = pyqtSignal(list)
    level_up = pyqtSignal()
    change_view = pyqtSignal()
    settings = pyqtSignal()
    new_folder = pyqtSignal()
    img_view = pyqtSignal(ImgViewItem)
    info = pyqtSignal(list)
    rearrange_grid = pyqtSignal()
    resize_grid = pyqtSignal()
    open_in_app = pyqtSignal(tuple)


class BtnNext(QGroupBox):
    clicked = pyqtSignal()
    icon_path = os.path.join(Static.internal_images_dir, "next.svg")
    icon_size = 16
    hh = 35

    def __init__(self, text: str):
        super().__init__()
        self.setFixedHeight(35)

        h_lay = QHBoxLayout(self)
        h_lay.setContentsMargins(2, 2, 6, 2)
        h_lay.setSpacing(2)

        text_widget = QLabel(text)
        h_lay.addWidget(text_widget)

        h_lay.addStretch()

        arrow = QSvgWidget()
        arrow.load(self.icon_path)
        arrow.setFixedSize(self.icon_size, self.icon_size)
        h_lay.addWidget(arrow)

    def mouseReleaseEvent(self, event):
        self.clicked.emit()
        return super().mouseReleaseEvent(event)
    

class GrayLabel(QLabel):
    def __init__(self, text: str):
        super().__init__(text)
        self.font_size_px = 9
        self._update_stylesheet()

    def _update_stylesheet(self):
        self.setStyleSheet(
            f"""
                color: rgba(128, 128, 128, 1.0);
                font-size: {self.font_size_px}px;
            """
        )

    def set_text_size(self, size_px: int = 9):
        self.font_size_px = size_px
        self._update_stylesheet()


class HoverGrayLabel(GrayLabel):
    def __init__(self, text: str):
        super().__init__(text)

    def _update_stylesheet(self):
        self.setStyleSheet(
            f"""
                HoverGrayLabel {{
                    color: rgba(128, 128, 128, 1.0);
                    font-size: {self.font_size_px}px;
                }}
                HoverGrayLabel:hover {{
                    /* palette(window-text) или palette(text) в зависимости от нужной роли палитры */
                    color: palette(window-text); 
                }}
            """
        )
