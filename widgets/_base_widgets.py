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
    """
    Базовые методы для GridStandart, GridSearch и GridList
    """
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
    sort_bar_update = pyqtSignal(object)
    fav_cmd_sig = pyqtSignal(tuple)
    load_st_grid_sig = pyqtSignal(tuple)
    move_slider_sig = pyqtSignal(int)
    change_view_sig = pyqtSignal(int)
    def __init__(self):
        """
        Базовый виджет с необходимыми сигналами для GridSearch и GridStandart
        """
        super().__init__()


class UTableView(QTableView, UMethods):
    new_history_item = pyqtSignal(str)
    path_bar_update = pyqtSignal(tuple)
    sort_bar_update = pyqtSignal(object)
    fav_cmd_sig = pyqtSignal(tuple)
    load_st_grid_sig = pyqtSignal(tuple)
    move_slider_sig = pyqtSignal(int)
    change_view_sig = pyqtSignal(int)
    def __init__(self):
        """
        Базовый виджет с необходимыми сигналами для GridList
        """
        super().__init__()


class UMenu(QMenu):
    """
    Кастомное контекстное меню: отключен правый клик, упрощен метод отображения
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
        Виджет однострочного ввода текста   
        Пользовательское контекстное меню: вырезать, копировать, вставить, выделить все     
        Кнопка "стереть" справа внутри поля ввода текста    
        Необходимо установить фиксированную ширину виджета и вызвать
        метод clear_btn_vcenter, чтобы кнока "стереть" заняла нужное положение
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
        Если есть хотя бы 1 символ в поле ввода текста, будет показана кнопка "стереть"
        """
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
        Виджет многострочного ввода текста  
        Пользовательское контекстное меню: вырезать, копировать, вставить, выделить все     
        Допускается только простой текст, форматирование текста при вставке
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


class UFrame(QFrame):
    object_name = "bar_top_btn"

    def __init__(self):
        """
        Стандартный QFrame с пользовательским стилем:   
        При наведении курсора мыши на виджет, он принимает выделенный стиль
        """
        super().__init__()
        self.setObjectName(UFrame.object_name)
        self.setStyleSheet(
            self.normal_style()
        )

    def normal_style(self):
        return f"""#{UFrame.object_name} {{
                        background: transparent;
                }}"""

    def solid_style(self):
        return f"""#{UFrame.object_name} {{
                        background: {Static.GRAY_GLOBAL}; 
                        border-radius: 7px;
                }}"""

    def enterEvent(self, a0):
        self.setStyleSheet(self.solid_style())

    def leaveEvent(self, a0):
        self.setStyleSheet(self.normal_style())


class WinBase(QWidget):
    def __init__(self):
        """
        Окно на основе QWidget с флагом ApplicationModal.  
        Оно блокирует взаимодействие с другими окнами приложения, пока открыто.
        """
        super().__init__()
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

    def center(self, parent: QWidget):
        """
        Центрирует текущее окно относительно родительского окна.
        """
        geo = self.geometry()
        geo.moveCenter(parent.geometry().center())
        self.setGeometry(geo)


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


class Sort:
    name = "name"
    type_ = "type_"
    size = "size"
    mod = "mod"
    rating = "rating"

    items: dict[str, str] = {
        name : "Имя",
        type_ : "Тип",
        size : "Размер",
        mod : "Дата изменения",
        rating : "Рейтинг"
    }


class BaseItem:
    def __init__(self, src: str, size: int, mod: int, rating: int):
        """
        Обязательные параметры для инициализации: 
        - set_src
        - set_name
        - set_file_type

        Базовый виджет, предшественник grid.py > Thumb.
        Используется для передачи данных между потоками и функциями.

        Пример использования:
        - В дополнительном потоке создаётся экземпляр класса BaseItem, которому присваивается имя "TEST" через атрибут name.
        - Этот экземпляр передаётся в основной поток через сигнал.
        - В основном потоке создаётся экземпляр класса Thumb (из модуля grid.py).
        - Атрибут name у Thumb устанавливается на основе значения BaseItem.name ("TEST").

        В BaseItem обязаны присутствовать все аттрибуты, соответствующие
        ключам Sort.items
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
        Сохраняет QPixmap, переданный, например, из дополнительного потока в основной.
        """
        self.pixmap_storage = pixmap

    def get_pixmap_storage(self):
        """
        Возвращает ранее сохранённый QPixmap.
        """
        return self.pixmap_storage

    def set_src(self):
        self.src = Utils.normalize_slash(self.src)

    def set_name(self):
        self.name = os.path.basename(self.src)

    def set_file_type(self):  
        if os.path.isdir(self.src):
            self.type_ = Static.FOLDER_TYPE
        else:
            _, self.type_ = os.path.splitext(self.src)

    @classmethod
    def check(cls):
        """
        Проверяет, содержит ли экземпляр BaseItem все атрибуты, 
        имена которых указаны в ключах словаря Sort.items.

        Это необходимо для корректной сортировки, так как она выполняется 
        по атрибутам, соответствующим ключам Sort.items.
        """
        base_item = BaseItem("/no/path/file.txt", 0, 0, 0)
        for column_name, _ in Sort.items.items():
            if not hasattr(base_item, column_name):
                t = [
                    "",
                    "", 
                    "base_widgets.py > BaseItem",
                    "В BaseItem не хватает аттрибута из Sort.items",
                    f"Аттрибут: {column_name}",
                    ""
                ]
                error_text = "\n".join(t)
                raise Exception (error_text)

    @classmethod
    def sort_items(cls, base_items: list["BaseItem"]) -> list["BaseItem"]:
        """
        Выполняет сортировку списка объектов BaseItem по заданному атрибуту.

        Пример:
        - Пользователь выбирает тип сортировки, например "По размеру", в меню SortMenu (actions.py).
        - SortMenu формируется на основе словаря Sort.items.
        - Выбранный пункт "По размеру" соответствует ключу "size" в Sort.items.
        - Ключ "size" — это имя атрибута в классе BaseItem.
        - Таким образом, сортировка осуществляется по значению атрибута "size" у объектов BaseItem.
        """
        
        attr = Dynamic.sort
        rev = Dynamic.rev

        if attr == Sort.name:

            # Особый случай: сортировка по имени
            # Разделяем элементы на две группы:
            # - те, чьё имя начинается с цифры (nums)
            # - все остальные (abc)
            nums: list[BaseItem] = []
            abc: list[BaseItem] = []

            for i in base_items:

                if i.name[0].isdigit():
                    nums.append(i)

                else:
                    abc.append(i)

            # Сортировка числовых имён по значению начальных цифр
            key_num = lambda base_item: cls.get_nums(base_item)

            # Сортировка остальных по алфавиту (по атрибуту 'name')
            key_abc = lambda base_item: getattr(base_item, attr)

            nums.sort(key=key_num, reverse=rev)
            abc.sort(key=key_abc, reverse=rev)

            # Объединяем отсортированные списки: сначала числовые, потом буквенные
            return [*nums, *abc]

        else:
            # Обычная сортировка по значению заданного атрибута
            key = lambda base_item: getattr(base_item, attr)
            base_items.sort(key=key, reverse=rev)
            return base_items

    @classmethod
    def get_nums(cls, base_item: "BaseItem"):
        """
        Извлекает начальные числа из имени base_item для числовой сортировки.
        Например: "123 Te99st33" → 123
        """
        return int(re.match(r'^\d+', base_item.name).group())