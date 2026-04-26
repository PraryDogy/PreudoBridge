import os

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QAction, QLabel, QLineEdit, QTextEdit

from cfg import Dynamic, Static
from system.items import ContextItem
from system.utils import Utils

from ._base_widgets import UMenu


class Reveal(QAction):
    text_ = "Показать в Finder"
    def __init__(self, parent: UMenu):
        super().__init__(self.text_, parent)


class WinInfo(QAction):
    text_ = "Инфо"
    def __init__(self, parent: UMenu):
        super().__init__(self.text_, parent)


class CopyPath(QAction):
    text_ = "Скопировать путь"
    def __init__(self, parent: UMenu):
        super().__init__(self.text_, parent)


class CopyName(QAction):
    text_ = "Скопировать имя"
    def __init__(self, parent: UMenu):
        super().__init__(self.text_, parent)


class OpenThumb(QAction):
    text_ = "Открыть"
    def __init__(self, parent: UMenu):
        super().__init__(self.text_, parent)


class FavRemove(QAction):
    text_ = "Удалить из избранного"
    def __init__(self, parent: UMenu):
        super().__init__(self.text_, parent)


class FavAdd(QAction):
    text_ = "Добавить в избранное"
    def __init__(self, parent: UMenu):
        super().__init__(self.text_, parent)


class OpenInApp(UMenu):
    text_menu = "Открыть в приложении"
    def_text = "Открыть по умолчанию"
    triggered = pyqtSignal(str)

    def __init__(self, parent: UMenu):
        super().__init__(parent=parent, title=self.text_menu)

        default = QAction(self.def_text, self)
        default.triggered.connect(lambda e: self.triggered.emit(""))
        self.addAction(default)
        self.addSeparator()

        for app_path in Dynamic.image_apps:
            wid = QAction(os.path.basename(app_path), self)
            wid.triggered.connect(
                lambda e, x=app_path: self.triggered.emit(x)
            )
            self.addAction(wid)


class CutText(QAction):
    text_ = "Вырезать"
    def __init__(self, parent: UMenu, widget: QLineEdit | QTextEdit):
        super().__init__(self.text_, parent)
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


class CopyText(QAction):
    text_ = "Копировать"
    def __init__(self, parent: UMenu, widget: QLineEdit | QLabel | QTextEdit):
        super().__init__(self.text_, parent)
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
        selection = selection.replace(Static.paragraph_symbol, "")
        selection = selection.replace(Static.line_feed_symbol, "")
        Utils.write_to_clipboard(selection)


# Вставить текст, допускается только QLineEdit и QTextEdit
class PasteText(QAction):
    text_ = "Вставить"
    def __init__(self, parent: UMenu, widget: QLineEdit | QTextEdit):
        super().__init__(self.text_, parent)
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


class SelectAllText(QAction):
    text_ = "Выделить все"
    def __init__(self, parent: UMenu, widget: QLineEdit | QTextEdit):
        super().__init__(self.text_, parent)
        self.wid = widget
        self.triggered.connect(lambda: self.wid.selectAll())


class SortMenu(UMenu):
    triggered = pyqtSignal()
    text_menu = "Сортировать"
    text_ascending = "По возрастанию"
    text_discenging = "По убыванию"

    def __init__(self, parent: UMenu, context_item: ContextItem):
        super().__init__(self.text_menu, parent)
        self.context_item = context_item
        ascending = QAction(self.text_ascending, self)
        # добавляем свойство прямой / обратной сортировки
        # прямая сортировка А > Я
        ascending.rev = False
        ascending.triggered.connect(lambda: self.cmd_revers(ascending.rev))

        descending = QAction(self.text_discenging, self)
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
            if i.rev == context_item.main_win_item.sort_item.reversed:
                i.setChecked(True)

        self.addSeparator()

        # true_name - имя колонки CACHE
        # text_name - текстовое обозначение колонки CACHE, основанное на
        # комментарии колонки (CACHE.column.comment)
        # смотри database.py > CACHE
        for true_name, text_name in context_item.main_win_item.sort_item.attr_lang.items():

            action_ = QAction(text_name, self)
            action_.setCheckable(True)

            # передаем true_name, чтобы осуществить сортировку сетки
            # и записать true_name в пользовательские .json настройки
            cmd_ = lambda e, true_name=true_name: self.cmd_sort(true_name)
            action_.triggered.connect(cmd_)

            if context_item.main_win_item.sort_item.item_type == true_name:
                action_.setChecked(True)

            self.addAction(action_)

    def cmd_sort(self, true_name: str):
        self.context_item.main_win_item.sort_item.item_type = true_name
        self.triggered.emit()

    def cmd_revers(self, reversed: bool):
        self.context_item.main_win_item.sort_item.reversed = reversed
        self.triggered.emit()


class ChangeViewMenu(UMenu):
    triggered = pyqtSignal(int)
    text_menu = "Вид"
    text_grid = "Сетка"
    text_list = "Список"

    def __init__(self, parent: UMenu, item: ContextItem):
        super().__init__(self.text_menu, parent)

        # отобразить сеткой
        grid_ = QAction(self.text_grid, self)
        grid_.triggered.connect(lambda: self.triggered.emit(0))
        grid_.setCheckable(True)
        self.addAction(grid_)

        # отобразить списком
        list_ = QAction(self.text_list, self)
        list_.triggered.connect(lambda: self.triggered.emit(1))
        list_.setCheckable(True)
        self.addAction(list_)

        # grid_view_type отвечает за тип отображения
        # 0 отображать сеткой, 1 отображать списком
        if item.main_win_item.view_mode == 0:
            grid_.setChecked(True)

        elif item.main_win_item.view_mode == 1:
            list_.setChecked(True)


class RotateMenu(UMenu):
    rotate_sig = pyqtSignal(int)
    text_menu = "Повернуть"
    clockwise = "Повернуть по ч.с. (⌘ + →)"
    counter_clockwise = "Повернуть против ч.с. (⌘ + ←)"

    def __init__(self, parent: UMenu):
        super().__init__(self.text_menu, parent)

        # отобразить сеткой
        grid_ = QAction(self.clockwise, self)
        grid_.triggered.connect(lambda: self.rotate_sig.emit(90))
        self.addAction(grid_)

        # отобразить списком
        list_ = QAction(self.counter_clockwise, self)
        list_.triggered.connect(lambda: self.rotate_sig.emit(-90))
        self.addAction(list_)


class NewMainWin(QAction):
    text_ = "Открыть в новом окне"
    def __init__(self, parent: UMenu):
        super().__init__(self.text_, parent)


class CutFiles(QAction):
    text_ = "Вырезать"
    def __init__(self, parent: UMenu):
        super().__init__(self.text_, parent)


class CopyFiles(QAction):
    text_ = "Скопировать"
    def __init__(self, parent: UMenu):
        super().__init__(self.text_, parent)


class RemoveFiles(QAction):
    text_ = "Удалить"
    def __init__(self, parent: UMenu):
        super().__init__(self.text_, parent)


class PasteFiles(QAction):
    text_ = "Вставить"
    def __init__(self, parent: UMenu):
        super().__init__(self.text_, parent)


class ShowInGrid(QAction):
    text_ = "Показать в папке"
    def __init__(self, parent: UMenu):
        super().__init__(self.text_, parent)


class UpdateGrid(QAction):
    text_ = "Обновить"
    def __init__(self, parent: UMenu):
        super().__init__(self.text_, parent)


class NewFolder(QAction):
    text_ = "Новая папка"
    def __init__(self, parent: UMenu):
        super().__init__(self.text_, parent)


class OpenSingle(QAction):
    text_ = "Открыть"
    def __init__(self, parent: UMenu):
        super().__init__(self.text_, parent)


class ImgConvert(QAction):
    text_ = "Создать копию jpg"
    def __init__(self, parent: UMenu):
        super().__init__(self.text_, parent)


class Rename(QAction):
    text_ = "Переименовать"
    def __init__(self, parent: UMenu):
        super().__init__(self.text_, parent)


class GridActions:
    def __init__(self, menu: UMenu, item: ContextItem):
        self.new_folder = NewFolder(menu)
        self.update_grid = UpdateGrid(menu)
        self.change_view = ChangeViewMenu(menu, item)
        self.sort_menu = SortMenu(menu, item)
        self.paste_files = PasteFiles(menu)


class CommonActions:
    def __init__(self, menu: UMenu, item: ContextItem):
        self.win_info = WinInfo(menu)
        self.reveal = Reveal(menu)
        self.copy_path = CopyPath(menu)
        self.copy_name = CopyName(menu)


class ThumbActions:
    def __init__(self, menu: UMenu, item: ContextItem):
        self.open_thumb = OpenThumb(menu)
        self.open_in_app_menu = OpenInApp(menu)
        self.convert_to_jpg = ImgConvert(menu)
        self.rename = Rename(menu)
        self.cut_files = CutFiles(menu)
        self.copy_files = CopyFiles(menu)
        self.remove_files = RemoveFiles(menu)

        self.new_main_win = NewMainWin(menu)
        self.fav_add = FavAdd(menu)
        self.fav_remove = FavRemove(menu)

        self.show_in_folder = ShowInGrid(menu)


class TextActions:
    def __init__(self):
        self.cut = CutText()
        self.copy = CopyText()
        self.paste = PasteText()
        self.select_all = SelectAllText()