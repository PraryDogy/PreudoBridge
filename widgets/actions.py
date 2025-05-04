import os
import subprocess

from PyQt5.QtCore import QRunnable, pyqtSignal
from PyQt5.QtWidgets import QAction, QLabel, QLineEdit, QTextEdit, QWidget

from cfg import Dynamic, Static
from utils import UThreadPool, Utils

from ._base_items import SortItem, UMenu


# Общий класс для выполнения действий QAction в отдельном потоке
class Task_(QRunnable):
    def __init__(self,  cmd_: callable):
        super().__init__()
        self.cmd_ = cmd_

    def run(self):
        self.cmd_()


class Tools:
    @classmethod
    def ensure_list(cls, value: str | list[str]) -> list[str]:
        """
        Гарантирует, что входное значение — список строк.

        Аргументы:
            - value: Строка или список строк.

        Возвращает:
            - Список строк.

        Примеры:
            - "example" → ["example"]
            - ["a", "b"] → ["a", "b"]
        """
        return [value] if isinstance(value, str) else value
    
    @classmethod
    def get_text(cls, text: str, value: list[str]) -> str:
        """
        Добавляет к переданному тексту количество элементов в списке.   
        Аргументы:  
            - text: Исходный текст (например, "скопировать объекты").     
            - urls: Список ссылок или объектов.   
        Возвращает:     
            - Строку в формате: "<текст> (<кол-во элементов в списке>)"   
            - Пример: "скопировать объекты (9)"
        """
        return f"{text} ({len(value)})"


class RevealInFinder(QAction):
    text_ = "Показать в Finder"
    def __init__(self, parent: UMenu, urls: str | list[str]):
        super().__init__(parent)
        self.urls = Tools.ensure_list(urls)
        text = Tools.get_text(RevealInFinder.text_, self.urls)
        self.setText(text)
        self.triggered.connect(self.files_cmd)

    def dir_cmd(self):
        subprocess.Popen(["open", self.urls[0]])

    def files_cmd(self):        
        cmd_=lambda: subprocess.run(["osascript", Static.REVEAL_SCPT] + self.urls)
        self.task_ = Task_(cmd_)
        UThreadPool.start(self.task_)


class Info(QAction):
    text_ = "Инфо"
    def __init__(self, parent: UMenu):
        super().__init__(Info.text_, parent)


# из родительского виджета копирует путь к файлу / папке
class CopyPath(QAction):
    text_ = "Скопировать путь"
    def __init__(self, parent: UMenu, urls: str | list):
        super().__init__(parent)
        self.urls = Tools.ensure_list(urls)
        text = Tools.get_text(CopyPath.text_, self.urls)
        self.setText(text)
        self.triggered.connect(self.cmd_)

    def cmd_(self, *args):
        Utils.write_to_clipboard("\n".join(self.urls))


class CopyName(QAction):
    text_ = "Скопировать имя"

    def __init__(self, parent: UMenu, names: str | list):
        super().__init__(parent)
        self.names = Tools.ensure_list(names)
        text = Tools.get_text(CopyName.text_, self.names)
        self.setText(text)
        self.triggered.connect(self.cmd_)

    def cmd_(self, *args):
        names = []
        for i in self.names:
            head, _ = os.path.splitext(i)
            names.append(head)
        Utils.write_to_clipboard("\n".join(names))


class View(QAction):
    text_ = "Просмотр"
    def __init__(self, parent: UMenu):
        super().__init__(View.text_, parent)


class FavRemove(QAction):
    text_ = "Удалить из избранного"
    def __init__(self, parent: UMenu):
        super().__init__(FavRemove.text_, parent)


class FavAdd(QAction):
    text_ = "Добавить в избранное"
    def __init__(self, parent: UMenu):
        super().__init__(FavAdd.text_, parent)


# Меню со списком приложений, при помощи которых можно открыть изображение
# Например Photoshop, стандартный просмотрщик Mac Os, Capture One
# список приложений формируется при инициации приложения
# смотри cfg.py
class OpenInApp(UMenu):
    rows_limit = 50
    text_menu = "Открыть в приложении"
    text_default = "По умолчанию"

    def __init__(self, parent: UMenu, src: str):
        super().__init__(parent=parent, title=OpenInApp.text_menu)
        self.src = src

        self.apps: dict[str, str] = {}
        self.setup_open_with_apps()
        self.apps = dict(sorted(self.apps.items()))
        self.apps = dict(list(self.apps.items())[:OpenInApp.rows_limit])

        open_default = QAction(OpenInApp.text_default, parent)
        open_default.triggered.connect(self.open_default_cmd)
        self.addAction(open_default)

        self.addSeparator()

        for name, app_path in self.apps.items():
            wid = QAction(name, self)
            cmd_ = lambda e, app_path=app_path: self.open_in_app_cmd(app_path)
            wid.triggered.connect(cmd_)
            self.addAction(wid)

    def setup_open_with_apps(self):
        for entry in os.scandir(Static.USER_APPS_DIR):
            if entry.name.endswith((".APP", ".app")):
                self.apps[entry.name] = entry.path

            elif entry.is_dir():
                for sub_entry in os.scandir(entry.path):
                    if sub_entry.name.endswith((".APP", ".app")):
                        self.apps[sub_entry.name] = sub_entry.path

    def open_in_app_cmd(self, app_path: str):
        # открыть в приложении, путь к которому указан в app_path
        cmd_=lambda: subprocess.call(["open", "-a", app_path, self.src])
        self.task_ = Task_(cmd_)
        UThreadPool.start(self.task_)

    def open_default_cmd(self):
        cmd_=lambda: subprocess.call(["open",  self.src])
        self.task_ = Task_(cmd_)
        UThreadPool.start(self.task_)


# меню с рейтингом для _grid.py > Thumb
class RatingMenu(UMenu):
    new_rating = pyqtSignal(int)
    text_ = "Рейтинг объектов"

    def __init__(self, parent: UMenu, urls: str | list, current_rating: int):
        super().__init__(parent=parent)
        urls = Tools.ensure_list(urls)
        text = Tools.get_text(RatingMenu.text_, urls)
        self.setTitle(text)

        # свойство Thumb
        # рейтинг для каждого виджета хранится в базе данных
        # и подгружается при создании сетки
        rating = current_rating

        cancel_ = QAction(Static.LINE_LONG_SYM, self)
        cancel_.triggered.connect(lambda: self.new_rating.emit(0))
        self.addAction(cancel_)

        # рейтинг от 1 до 5 звезд
        # в цикле происходит проверка, есть ли рейтинг > 0
        # в rating (свойство Thumb)
        # если есть, то отмечается setChecked
        # 0 возвращает False
        for current_rating in range(1, 6):
            wid = QAction(Static.STAR_SYM * current_rating, self)
            wid.setCheckable(True)

            if rating == current_rating:
                wid.setChecked(True)

            # клик возвращает через сигнал целое число
            # соответствующее количеству звезд
            # например: int(5) это 5 звезд = rating в данном цикле
            # виджет Thumb установит новый рейтинг и 
            # запишет его в базу данных
            cmd_ = lambda e, r=current_rating: self.new_rating.emit(r)
            wid.triggered.connect(cmd_)
            self.addAction(wid)


# удалить текст из виджета и скопировать в буфер обмена удаленную часть текста
# только для QLineEdit / QTextEdit
class CutText(QAction):
    text_ = "Вырезать"
    def __init__(self, parent: UMenu, widget: QLineEdit | QTextEdit):
        super().__init__(CutText.text_, parent)
        self.wid = widget
        self.triggered.connect(self.cmd_)

    def cmd_(self):
        if isinstance(self.wid, QLineEdit):
            selection = self.wid.selectedText()
            text = self.wid.text().replace(selection, "")
            self.wid.setText(text)

        elif isinstance(self.wid, QTextEdit):
            selection = self.wid.textCursor().selectedText()
            self.wid.textCursor().removeSelectedText()

        Utils.write_to_clipboard(selection)


# Копировать выделенный текст в буфер обмена
# Допускается QLabel с возможностью выделения текста
class CopyText(QAction):
    text_ = "Копировать"
    def __init__(self, parent: UMenu, widget: QLineEdit | QLabel | QTextEdit):
        super().__init__(CopyText.text_, parent)
        self.wid = widget
        self.triggered.connect(self.cmd_)

    def cmd_(self):
        if isinstance(self.wid, QTextEdit):
            selection = self.wid.textCursor().selectedText()
        else:
            selection = self.wid.selectedText()

        # это два символа, которые в PyQt5 почему то обозначаются
        # символами параграфа и новой строки
        # при копировании мы удаляем их, делая копируемый текст
        # однострочным
        selection = selection.replace(Static.PARAGRAPH_SEP, "")
        selection = selection.replace(Static.LINE_FEED, "")
        Utils.write_to_clipboard(selection)


# Вставить текст, допускается только QLineEdit и QTextEdit
class PasteText(QAction):
    text_ = "Вставить"
    def __init__(self, parent: UMenu, widget: QLineEdit | QTextEdit):
        super().__init__(PasteText.text_, parent)
        self.wid = widget
        self.triggered.connect(self.cmd_)

    def cmd_(self):
        text = Utils.read_from_clipboard()

        if isinstance(self.wid, QTextEdit):
            cursor = self.wid.textCursor()
            cursor.insertText(text)
        else:
            new_text = self.wid.text() + text
            self.wid.setText(new_text)


class TextSelectAll(QAction):
    text_ = "Выделить все"
    def __init__(self, parent: UMenu, widget: QLineEdit | QTextEdit):
        super().__init__(TextSelectAll.text_, parent)
        self.wid = widget
        self.triggered.connect(lambda: self.wid.selectAll())


class SortMenu(UMenu):
    sort_grid_sig = pyqtSignal()
    rearrange_grid_sig = pyqtSignal()
    sort_bar_update_sig = pyqtSignal(object)
    text_menu = "Сортировать"
    text_ascending = "По возрастанию"
    text_discenging = "По убыванию"

    def __init__(self, parent: UMenu, sort_item: SortItem):
        super().__init__(SortMenu.text_menu, parent)
        self.sort_item = sort_item

        ascending = QAction(SortMenu.text_ascending, self)
        # добавляем свойство прямой / обратной сортировки
        # прямая сортировка А > Я
        ascending.rev = False
        ascending.triggered.connect(lambda: self.cmd_revers(ascending.rev))

        descending = QAction(SortMenu.text_discenging, self)
        # добавляем свойство прямой / обратной сортировки
        # обратная сортировка Я > А
        descending.rev = True
        descending.triggered.connect(lambda: self.cmd_revers(descending.rev))

        for i in (ascending, descending):
            i.setCheckable(True)
            self.addAction(i)

            # если свойство rev совпадает с пользовательским свойством reversed
            # то отмечаем галочкой
            # JsonData - пользовательские данные из .json файла
            if i.rev == self.sort_item.get_rev():
                i.setChecked(True)

        self.addSeparator()

        # true_name - имя колонки CACHE
        # text_name - текстовое обозначение колонки CACHE, основанное на
        # комментарии колонки (CACHE.column.comment)
        # смотри database.py > CACHE
        for true_name, text_name in SortItem.lang_dict.items():

            action_ = QAction(text_name, self)
            action_.setCheckable(True)

            # передаем true_name, чтобы осуществить сортировку сетки
            # и записать true_name в пользовательские .json настройки
            cmd_ = lambda e, true_name=true_name: self.cmd_sort(true_name)
            action_.triggered.connect(cmd_)

            if self.sort_item.get_sort() == true_name:
                action_.setChecked(True)

            self.addAction(action_)

    def cmd_sort(self, true_name: str):
        # записываем true_name (тип сортировки) в пользовательский .json
        self.sort_item.set_sort(true_name)
        self.sort_grid_sig.emit()
        self.rearrange_grid_sig.emit()
        self.sort_bar_update_sig.emit(None)

    def cmd_revers(self, reversed: bool):
        # записываем порядок сортировки в пользовательский .json
        self.sort_item.set_rev(reversed)
        self.sort_grid_sig.emit()
        self.rearrange_grid_sig.emit()
        self.sort_bar_update_sig.emit(None)


# показать сетку / список - GridStandart / GridSearch / ListFileSystem
# list_file_system.py > ListFileSystem
class ChangeViewMenu(UMenu):
    change_view_sig = pyqtSignal(int)
    text_menu = "Вид"
    text_grid = "Сетка"
    text_list = "Список"

    def __init__(self, parent: UMenu, view_index: int):
        super().__init__(ChangeViewMenu.text_menu, parent)

        # отобразить сеткой
        grid_ = QAction(ChangeViewMenu.text_grid, self)
        grid_.triggered.connect(lambda: self.change_view_sig.emit(0))
        grid_.setCheckable(True)
        self.addAction(grid_)

        # отобразить списком
        list_ = QAction(ChangeViewMenu.text_list, self)
        list_.triggered.connect(lambda: self.change_view_sig.emit(1))
        list_.setCheckable(True)
        self.addAction(list_)

        # grid_view_type отвечает за тип отображения
        # 0 отображать сеткой, 1 отображать списком
        if view_index == 0:
            grid_.setChecked(True)

        elif view_index == 1:
            list_.setChecked(True)


class OpenInNewWindow(QAction):
    text_ = "Открыть в новом окне"
    def __init__(self, parent: UMenu):
        super().__init__(OpenInNewWindow.text_, parent)


class CopyObjects(QAction):
    text_ = "Скопировать объекты"
    def __init__(self, parent: UMenu, urls: list[str] | str):
        super().__init__(parent)
        urls = Tools.ensure_list(urls)
        text = Tools.get_text(CopyObjects.text_, urls)
        self.setText(text)


class RemoveObjects(QAction):
    text_ = "Удалить объекты"
    def __init__(self, parent: UMenu, urls: list[str] | str):
        super().__init__(parent)
        self.urls = Tools.ensure_list(urls)
        text = Tools.get_text(RemoveObjects.text_, self.urls)
        self.setText(text)


class PasteObjects(QAction):
    text_ = "Вставить объекты"
    def __init__(self, parent: UMenu, urls: list[str] | str):
        super().__init__(parent)
        text = Tools.get_text(PasteObjects.text_, urls)
        self.setText(text)


class ShowInGrid(QAction):
    text_ = "Показать в папке"
    def __init__(self, parent: UMenu):
        super().__init__(parent)
        self.setText(ShowInGrid.text_)


class UpdateGrid(QAction):
    text_ = "Обновить"
    def __init__(self, parent: UMenu):
        super().__init__(UpdateGrid.text_, parent)


class ItemActions:
    View = View

    OpenInApp = OpenInApp
    OpenInNewWindow = OpenInNewWindow
    # "Separator"

    Info = Info
    RevealInFinder = RevealInFinder
    CopyPath = CopyPath
    CopyName = CopyName
    CopyObjects = CopyObjects
    # "Separator"

    # если это папка
    FavRemove = FavRemove
    FavAdd = FavAdd
    # "Separator"

    RatingMenu = RatingMenu
    # "Separator"

    # если это сетка GridSearch
    ShowInGrid = ShowInGrid
    # "Separator"

    RemoveObjects = RemoveObjects


class GridActions:
    Info = Info
    # "Separator"

    RevealInFinder = RevealInFinder
    CopyPath = CopyPath
    CopyName = CopyName
    # "Separator"

    FavRemove = FavRemove
    FavAdd = FavAdd
    # "Separator"

    ChangeViewMenu = ChangeViewMenu
    SortMenu = SortMenu
    # "Separator"

    # Если есть Grid.urls_to_copy и если это не GridSearch
    PasteObjects = PasteObjects
    UpdateGrid = UpdateGrid