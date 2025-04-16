import os
import re

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import (QContextMenuEvent, QCursor, QMouseEvent, QPixmap,
                         QWheelEvent)
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import (QFrame, QLineEdit, QMenu, QScrollArea, QSlider,
                             QTableView, QTextEdit, QWidget)

from cfg import Dynamic, Static
from database import ColumnNames
from utils import Utils


class UMethods:
    def order_(self, *args, **kwargs):
        raise Exception("Переопредели метод sort_grid")

    def filter_(self, *args, **kwargs):
        raise Exception("Переопредели метод filter_grid")

    def resize_(self, *args, **kwargs):
        raise Exception("Переопредели метод resize_grid")
    
    def rearrange(self, *args, **kwargs):
        raise Exception("Переопредели метод rearrange")


# Сигналы в UScrollArea и UTableView должны быть идентичны

class UScrollArea(QScrollArea, UMethods):
    new_history_item = pyqtSignal(str)
    path_bar_update = pyqtSignal(str)
    fav_cmd_sig = pyqtSignal(tuple)
    load_st_grid_sig = pyqtSignal(tuple)
    move_slider_sig = pyqtSignal(int)
    change_view_sig = pyqtSignal(int)
    def __init__(self):
        super().__init__()


class UTableView(QTableView, UMethods):
    new_history_item = pyqtSignal(str)
    bar_bottom_update = pyqtSignal(tuple)
    fav_cmd_sig = pyqtSignal(tuple)
    load_st_grid_sig = pyqtSignal(tuple)
    move_slider_sig = pyqtSignal(int)
    change_view_sig = pyqtSignal(int)
    def __init__(self):
        super().__init__()


class UMenu(QMenu):
    def show_(self):
        self.exec_(QCursor.pos())

    def mouseReleaseEvent(self, a0):
        if a0.button() == Qt.MouseButton.RightButton:
            a0.ignore()
        else:
            super().mouseReleaseEvent(a0)


class USlider(QSlider):
    def __init__(self, orientation: Qt.Orientation, minimum: int, maximum: int):
        super().__init__(orientation=orientation, parent=None, minimum=minimum, maximum=maximum)

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
    def __init__(self, src: str = None, size: int = None):
        super().__init__()
        self.setStyleSheet(f"""background-color: transparent;""")
        self.renderer().setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        if src:
            self.load(src)
        if size:
            self.setFixedSize(size, size)


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
        """
        Перемещает кнопку "стереть" вертикально по центру и к правой стороне
        """
        x = self.width() - self.clear_btn.width() - 6
        y = (self.height() - self.clear_btn.height()) // 2
        self.clear_btn.move(x, y)

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:
        # предотвращаем круговой импорт
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
        super().__init__()
        self.setAcceptRichText(False)
        # self.setStyleSheet("padding-left: 2px; padding-right: 18px;")

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:
        # предотвращаем круговой импорт
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
                        background: {Static.GRAY_GLOBAL}; 
                        border-radius: 7px;
                }}"""

    def enterEvent(self, a0):
        self.setStyleSheet(
            self.solid_style()
        )

    def leaveEvent(self, a0):

        self.setStyleSheet(
            self.normal_style()
        )


class WinBase(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

    def center(self, parent: QWidget):
        geo = self.geometry()
        geo.moveCenter(parent.geometry().center())
        self.setGeometry(geo)


class MinMaxDisabledWin(WinBase):
    def __init__(self):
        super().__init__()
        fl = Qt.WindowType.Window | Qt.WindowType.CustomizeWindowHint
        fl = fl  | Qt.WindowType.WindowCloseButtonHint
        self.setWindowFlags(fl)


class BaseItem:
    def __init__(self, src: str, size: int, mod: int, rating: int):
        """
        Обязательно задать параметры:   
        set_src, set_name, set_file_type    
        """
        super().__init__()
        self.src: str = src

        self.size: int = int(size)
        self.mod: int = int(mod)
        self.rating: int = rating

        self.type_: str = None
        self.name: str = None
        self.pixmap_storage: QPixmap = None

    def set_pixmap_storage(self, pixmap: QPixmap):
        """
        Данный аттрибут нужен для обмена QPixmap между родительским BaseItem
        и наследуемым классом
        """
        self.pixmap_storage = pixmap

    def get_pixmap_storage(self):
        """
        Данный аттрибут нужен для обмена QPixmap между родительским BaseItem
        и наследуемым классом
        """
        return self.pixmap_storage

    def set_src(self):
        self.src = Utils.normalize_slash(self.src)

    def set_name(self):
        self.name = os.path.basename(self.src)

    def set_file_type(self):
        # Проверка: если путь ведёт к директории, то задаём тип FOLDER_TYPE.
        # Иначе определяем тип по расширению файла (например, ".txt").    
        if os.path.isdir(self.src):
            self.type_ = Static.FOLDER_TYPE
        else:
            _, self.type_ = os.path.splitext(self.src)

    # Как работает сортировка:
    # пользователь выбрал сортировку "по размеру"
    # в Dynamic в аттрибут "sort" записывается значение "size"
    # CACHE колонка имеет имя "size"
    # OrderItem имеет аттрибут "size"
    # на основе аттрибута "size" происходит сортировка списка из OrderItem

    @classmethod
    def sort_items(cls, base_items: list["BaseItem"]) -> list["BaseItem"]:
        
        attr = Dynamic.sort
        rev = Dynamic.rev

        if attr == ColumnNames.NAME:

            # сортировка по имени:
            # создаем список элементов, у которых в начале числовые символы
            # и список элементов, у которых в начале нечисловые символы
            # сортируем каждый список по отдельности
            # возвращаем объединенный список

            nums: list[BaseItem] = []
            abc: list[BaseItem] = []

            for i in base_items:

                if i.name[0].isdigit():
                    nums.append(i)

                else:
                    abc.append(i)

            # сортировка по числам в начале OrderItem.name
            key_num = lambda base_item: cls.get_nums(base_item)

            # сортировка по OrderItem.name
            key_abc = lambda base_item: getattr(base_item, attr)

            nums.sort(key=key_num, reverse=rev)
            abc.sort(key=key_abc, reverse=rev)

            return [*nums, *abc]

        else:

            key = lambda base_item: getattr(base_item, attr)
            base_items.sort(key=key, reverse=rev)
            return base_items

    # извлекаем начальные числа из base_item.name
    # по которым будет сортировка, например: "123 Te99st33" > 123
    # re.match ищет числа до первого нечислового символа
    @classmethod
    def get_nums(cls, base_item: "BaseItem"):

        return int(
            re.match(r'^\d+', base_item.name).group()
        )