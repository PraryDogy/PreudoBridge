import os
import re

from PyQt5.QtCore import QRunnable, Qt, QThreadPool, pyqtSignal, QTimer
from PyQt5.QtGui import (QContextMenuEvent, QCursor, QMouseEvent, QPixmap,
                         QWheelEvent)
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import (QFrame, QLineEdit, QMenu, QScrollArea, QSlider,
                             QTableView, QTextEdit, QWidget)

from cfg import Dynamic, Static
from utils import Utils


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


class SortItem:
    """
    Класс, содержащий перечень доступных атрибутов для сортировки элементов.

    Правила добавления/удаления атрибута:

    - Каждый атрибут задаётся как строковая константа (например, name = "name"),
      чтобы избежать ручного ввода строк по всему коду. Вместо строки "name" 
      можно использовать Sort.name — это безопаснее и удобнее при поддержке проекта.

    - Словарь `items` содержит список доступных сортировок:
        • ключ — техническое имя поля, берётся из атрибутов класса Sort (например, Sort.name);
        • значение — человекочитаемое название, отображаемое в интерфейсе (например, "Имя").

    - При добавлении или удалении атрибута:
        • добавьте/удалите соответствующую строковую константу в классе Sort;
        • добавьте/удалите соответствующую запись в словаре `items`;
        • обязательно добавьте/удалите соответствующий атрибут в классе BaseItem.

    Пример добавления нового поля сортировки:
    - Нужно добавить сортировку по дате последнего открытия.
        • Добавьте в Sort: `last_open = "last_open"`
        • Добавьте в items: `last_open: "Дата последнего открытия"`
        • Добавьте в BaseItem: `self.last_open = None`
        • Реализуйте логику заполнения поля, например, через os.stat
    """

    name = "name"
    type_ = "type_"
    size = "size"
    mod = "mod"
    birth = "birth"
    rating = "rating"

    lang_dict: dict[str, str] = {
        name : "Имя",
        type_ : "Тип",
        size : "Размер",
        mod : "Дата изменения",
        birth: "Дата создания",
        rating : "Рейтинг",
    }

    def __init__(self):
        """
        Объект для сортировки. По умолчанию: sort "name", rev False
        """
        super().__init__()
        self.sort: str = SortItem.name
        self.rev: bool = False

    def set_rev(self, value: bool):
        if isinstance(value, bool):
            self.rev = value
        else:
            raise Exception("только bool")
        
    def get_rev(self):
        return self.rev

    def set_sort(self, value: str):
        if isinstance(value, str):
            self.sort = value
        else:
            raise Exception("только str")
        
    def get_sort(self):
        return self.sort


class BaseItem:
    def __init__(self, src: str, rating: int = 0):
        """
        Вызовите setup_attrs после инициации экземпляра класса.     

        Базовый виджет, предшественник grid.py > Thumb.
        Используется для передачи данных между потоками и функциями.

        Пример использования:
        - В дополнительном потоке создаётся экземпляр класса BaseItem
        - Экземпляру присваивается имя "TEST" через атрибут name.
        - Этот экземпляр передаётся в основной поток через сигнал.
        - В основном потоке создаётся экземпляр класса Thumb (из модуля grid.py).
        - Атрибут name у Thumb устанавливается на основе значения BaseItem.name ("TEST").

        В BaseItem обязаны присутствовать все аттрибуты, соответствующие Sort.items
        """
        super().__init__()
        self.src: str = src
        self.name: str = None
        self.type_: str = None
        self.rating: int = rating
        self.mod: int = None
        self.birth: int = None
        self.size: int = None
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

    def setup_attrs(self):
        """
        Устанавливает параметры: src, name, type_, mod, birth, size, rating
        """
        self.src = Utils.normalize_slash(self.src)
        self.name = os.path.basename(self.src)

        if os.path.isdir(self.src):
            self.type_ = Static.FOLDER_TYPE
        else:
            _, self.type_ = os.path.splitext(self.src)

        stat = os.stat(self.src)
        self.mod = stat.st_mtime
        self.birth = stat.st_birthtime
        self.size = stat.st_size

        # Поправка старой системы рейтинга, когда рейтинг был двузначным
        self.rating = self.rating % 10

    @classmethod
    def check(cls):
        """
        Проверяет, содержит ли экземпляр BaseItem все атрибуты, 
        имена которых указаны в ключах словаря Sort.items.

        Это необходимо для корректной сортировки, так как она выполняется 
        по атрибутам, соответствующим ключам Sort.items.
        """
        base_item = BaseItem("/no/path/file.txt")
        for column_name, _ in SortItem.lang_dict.items():
            if not hasattr(base_item, column_name):
                raise Exception (f"\n\nbase_widgets.py > BaseItem: не хватает аттрибута из Sort.items. Аттрибут: {column_name}\n\n")

    @classmethod
    def sort_(cls, base_items: list["BaseItem"], sort_item: SortItem) -> list["BaseItem"]:
        """
        Выполняет сортировку списка объектов BaseItem по заданному атрибуту.

        Пример:
        - Пользователь выбирает тип сортировки, например "По размеру", в меню SortMenu (actions.py).
        - SortMenu формируется на основе словаря Sort.items (в этом файле, выше).
        - Выбранный пункт "По размеру" соответствует ключу "size" в Sort.items.
        - Ключ "size" — это имя атрибута в классе BaseItem.
        - Таким образом, сортировка осуществляется по значению атрибута "size" у объектов BaseItem.
        """
        
        attr = sort_item.sort
        rev = sort_item.rev

        if attr == SortItem.name:

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
    

class USep(QFrame):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background: rgba(0, 0, 0, 0.2)")
        self.setFixedHeight(1)


class SearchItem:
    SEARCH_LIST_TEXT = "Найти по списку"
    SEARCH_EXTENSIONS = {
        "Найти jpg": Static.ext_jpeg,
        "Найти png": Static.ext_png,
        "Найти tiff": Static.ext_tiff,
        "Найти psd/psb": Static.ext_psd,
        "Найти raw": Static.ext_raw,
        "Найти видео": Static.ext_video,
        "Найти любые фото": Static.ext_all
    }

    def __init__(self):
        super().__init__()
        self._filter: int = 0
        self._content: str | list[str] = None

    def get_content(self):
        """
        none    
        str: искать текст   
        tuple[str]: искать по расширениям   
        list[str]: искать по списку 
        """
        return self._content

    def set_content(self, value: str | tuple[str] | list[str]):
        """
        none    
        str: искать текст   
        tuple: искать по расширениям    
        list[str]: искать по списку     
        """
        self._content = value
    
    def set_filter(self, value: int):
        """
        0: нет фильтра      
        1: точное соответствие  
        2: искомый текст содержится в имени и наоборот  
        """
        self._filter = value

    def get_filter(self):
        """
        0: нет фильтра  
        1: точное соответствие  
        2: искомый текст содержится в имени и наоборот  
        """
        return self._filter
    
    def reset(self):
        self.set_content(None)
        self.set_filter(0)


class MainWinItem:
    def __init__(self):
        self._urls: list[str] = []
        self._go_to: str = None
        self.main_dir: str = None
        self.scroll_value: int = None

    def set_urls(self, urls: list[str]):
        self._urls = urls

    def get_urls(self):
        return self._urls

    def set_go_to(self, path: str):
        self._go_to = path

    def get_go_to(self):
        return self._go_to
    
    def clear_urls(self):
        self._urls.clear()

    def clear_go_to(self):
        self._go_to = None


class URunnable(QRunnable):
    def __init__(self):
        """
        Переопределите метод task().
        Не переопределяйте run().
        """
        super().__init__()
        self.should_run__ = True
        self.finished__ = False

    def is_should_run(self):
        return self.should_run__
    
    def set_should_run(self, value: bool):
        self.should_run__ = value

    def set_finished(self, value: bool):
        self.finished__ = value

    def is_finished(self):
        return self.finished__
    
    def run(self):
        try:
            self.task()
        finally:
            self.set_finished(True)
            if self in UThreadPool.tasks:
                QTimer.singleShot(5000, lambda: UThreadPool.tasks.remove(self))

    def task(self):
        raise NotImplementedError("Переопредели метод task() в подклассе.")


class UThreadPool:
    pool: QThreadPool = None
    tasks: list[URunnable] = []

    @classmethod
    def init(cls):
        cls.pool = QThreadPool.globalInstance()

    @classmethod
    def start(cls, runnable: QRunnable):
        cls.tasks.append(runnable)
        cls.pool.start(runnable)
