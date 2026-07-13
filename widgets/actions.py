import os

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QAction

from cfg import Dynamic
from system.items import MainWinItem

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



class SelectAllText(QAction):
    text_ = "Выделить все"
    def __init__(self, parent: UMenu):
        super().__init__(self.text_, parent)


class CopyText(QAction):
    text_ = "Скопировать"
    def __init__(self, parent: UMenu):
        super().__init__(self.text_, parent)


class SortMenu(UMenu):
    triggered = pyqtSignal()
    text_menu = "Сортировать"
    text_ascending = "По возрастанию"
    text_discenging = "По убыванию"

    def __init__(self, parent: UMenu, main_win_item: MainWinItem):
        super().__init__(self.text_menu, parent)
        self.sort_item = main_win_item.sort_item
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
            if i.rev == self.sort_item.reversed:
                i.setChecked(True)

        self.addSeparator()

        # true_name - имя колонки CACHE
        # text_name - текстовое обозначение колонки CACHE, основанное на
        # комментарии колонки (CACHE.column.comment)
        # смотри database.py > CACHE
        for true_name, text_name in self.sort_item.attr_lang.items():

            action_ = QAction(text_name, self)
            action_.setCheckable(True)

            # передаем true_name, чтобы осуществить сортировку сетки
            # и записать true_name в пользовательские .json настройки
            cmd_ = lambda e, true_name=true_name: self.cmd_sort(true_name)
            action_.triggered.connect(cmd_)

            if self.sort_item.item_type == true_name:
                action_.setChecked(True)

            self.addAction(action_)

    def cmd_sort(self, true_name: str):
        self.sort_item.item_type = true_name
        self.triggered.emit()

    def cmd_revers(self, reversed: bool):
        self.sort_item.reversed = reversed
        self.triggered.emit()


class ChangeViewMenu(UMenu):
    triggered = pyqtSignal(int)
    text_menu = "Вид"
    text_grid = "Сетка"
    text_list = "Список"

    def __init__(self, parent: UMenu, main_win_item: MainWinItem):
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
        if main_win_item.view_mode == 0:
            grid_.setChecked(True)

        elif main_win_item.view_mode == 1:
            list_.setChecked(True)


# class RotateMenu(UMenu):
#     triggered = pyqtSignal(int)
#     text_menu = "Повернуть"
#     clockwise = "Повернуть по ч.с. (⌘ + →)"
#     counter_clockwise = "Повернуть против ч.с. (⌘ + ←)"

#     def __init__(self, parent: UMenu):
#         super().__init__(self.text_menu, parent)

#         # отобразить сеткой
#         grid_ = QAction(self.clockwise, self)
#         grid_.triggered.connect(lambda: self.triggered.emit(90))
#         self.addAction(grid_)

#         # отобразить списком
#         list_ = QAction(self.counter_clockwise, self)
#         list_.triggered.connect(lambda: self.triggered.emit(-90))
#         self.addAction(list_)


class RotateCW(QAction):
    text_ = "Повернуть по ч.с. (⌘ + →)"
    def __init__(self, parent: UMenu):
        super().__init__(self.text_, parent)


class RotateCCW(QAction):
    text_ = "Повернуть против ч.с. (⌘ + ←)"
    def __init__(self, parent: UMenu):
        super().__init__(self.text_, parent)


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


class UpdateThumb(QAction):
    text_ = "Обновить данные"
    def __init__(self, parent: UMenu):
        super().__init__(self.text_, parent)


class Actions:
    def __init__(self, menu: UMenu):
        self.copy_text = CopyText(menu)
        self.select_all_text = SelectAllText(menu)

        self.fav_add = FavAdd(menu)
        self.fav_remove = FavRemove(menu)
        self.open_thumb = OpenThumb(menu)
        self.convert_to_jpg = ImgConvert(menu)
        self.rename = Rename(menu)
        self.cut_files = CutFiles(menu)
        self.copy_files = CopyFiles(menu)
        self.remove_files = RemoveFiles(menu)
        self.new_main_win = NewMainWin(menu)
        self.fav_add = FavAdd(menu)
        self.fav_remove = FavRemove(menu)
        self.show_in_folder = ShowInGrid(menu)
        self.win_info = WinInfo(menu)
        self.reveal = Reveal(menu)
        self.copy_path = CopyPath(menu)
        self.copy_name = CopyName(menu)
        self.new_folder = NewFolder(menu)
        self.update_grid = UpdateGrid(menu)
        self.paste_files = PasteFiles(menu)
        self.rotate_cw = RotateCW(menu)
        self.rotate_ccw = RotateCCW(menu)
        self.update_thumb = UpdateThumb(menu)


class Menus:
    def __init__(self, menu: UMenu, main_win_item: MainWinItem = None):
        if main_win_item:
            self.change_view = ChangeViewMenu(menu, main_win_item)
            self.sort_menu = SortMenu(menu, main_win_item)
        self.open_in_app_menu = OpenInApp(menu)
        # self.rotate_menu = RotateMenu(menu)