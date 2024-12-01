import subprocess

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QAction, QLineEdit, QMenu

from cfg import COLORS, IMAGE_APPS, STAR_SYM, Dynamic, JsonData
from database import ORDER
from signals import SignalsApp
from utils import URunnable, UThreadPool, Utils

REVEAL_T = "Показать в Finder"
INFO_T = "Свойства"
COPY_PATH_T = "Скопировать путь"
VIEW_T = "Просмотр"
OPEN_IN_APP_T = "Открыть в приложении"
COLORS_T = "Цвета"
RATING_T = "Рейтинг"
SHOW_IN_FOLDER_T = "Показать в папке"
FAV_REMOVE_T = "Удалить из избранного"
FAV_ADD_T = "Добавить в избранное"
RENAME_T = "Переименовать"
CUT_T = "Вырезать"
COPY_T = "Копировать"
PASTE_T = "Вставить"
SELECT_ALL_T = "Выделить все"
SORT_T = "Сортировать"
ARROW_DOWN = "\U00002193"
ARROW_TOP = "\U00002191"
ASCENDING_T = "По возрастанию"
DISCENDING_T = "По убыванию"
UPDATE_GRID_T = "Обновить"
CHANGE_VIEW_T = "Вид"
CHANGE_VIEW_GRID_T = "Сетка"
CHANGE_VIEW_LIST_T = "Список"

class Task_(URunnable):
    def __init__(self,  cmd_: callable):
        super().__init__()
        self.cmd_ = cmd_

    @URunnable.set_running_state
    def run(self):
        self.cmd_()


class UAction(QAction):
    def __init__(self, parent: QMenu, src: str, text: str):
        super().__init__(parent=parent, text=text)
        self.triggered.connect(self.cmd_)
        self.src = src

    def cmd_(self):
        raise Exception("_actions > Переназначь cmd_")


class RevealInFinder(UAction):
    def __init__(self, parent: QMenu, src: str):
        super().__init__(parent, src, REVEAL_T)

    def cmd_(self):
        cmd_ = lambda: subprocess.call(["open", "-R", self.src])
        task_ = Task_(cmd_)
        UThreadPool.pool.start(task_)


class Info(UAction):
    def __init__(self, parent: QMenu, src: str):
        super().__init__(parent, src, INFO_T)

    def cmd_(self):
        from ._base import OpenWin
        OpenWin.info(Utils.get_main_win(), self.src)


class CopyPath(UAction):
    def __init__(self, parent: QMenu, src: str):
        super().__init__(parent, src, COPY_PATH_T)

    def cmd_(self):
        Utils.write_to_clipboard(self.src)


class View(UAction):
    _clicked = pyqtSignal()

    def __init__(self, parent: QMenu, src: str):
        super().__init__(parent, src, VIEW_T)

    def cmd_(self):
        self._clicked.emit()


class ShowInFolder(UAction):
    _clicked = pyqtSignal()

    def __init__(self, parent: QMenu, src: str):
        super().__init__(parent, src, SHOW_IN_FOLDER_T)

    def cmd_(self):
        self._clicked.emit()


class FavRemove(UAction):
    _clicked = pyqtSignal()

    def __init__(self, parent: QMenu, src: str):
        super().__init__(parent, src, FAV_REMOVE_T)

    def cmd_(self):
        self._clicked.emit()


class Rename(UAction):
    _clicked = pyqtSignal()

    def __init__(self, parent: QMenu, src: str):
        super().__init__(parent, src, RENAME_T)

    def cmd_(self):
        self._clicked.emit()


class FavAdd(UAction):
    _clicked = pyqtSignal()

    def __init__(self, parent: QMenu, src: str):
        super().__init__(parent, src, FAV_ADD_T)

    def cmd_(self):
        self._clicked.emit()


class UpdateGrid(UAction):
    def __init__(self, parent: QMenu, src: str):
        super().__init__(parent, src, UPDATE_GRID_T)

    def cmd_(self):
        SignalsApp.all_.load_standart_grid.emit("")


class OpenInApp(QMenu):
    def __init__(self, parent: QMenu, src: str):
        super().__init__(parent=parent, title=OPEN_IN_APP_T)
        self.src = src

        for name, app_path in IMAGE_APPS.items():
            wid = QAction(parent=self, text=name)
            wid.triggered.connect(lambda e, a=app_path: self.cmd_(a))
            self.addAction(wid)

    def cmd_(self, app_path: str):
        cmd_ = lambda: subprocess.call(["open", "-a", app_path, self.src])
        task_ = Task_(cmd_)
        UThreadPool.pool.start(task_)


class ColorMenu(QMenu):
    _clicked = pyqtSignal(str)

    def __init__(self, parent: QMenu, src: str, colors: str):
        super().__init__(parent=parent, title=COLORS_T)
        self.src = src
        self.colors = colors

        for color, text in COLORS.items():

            wid = QAction(parent=self, text=f"{color} {text}")
            wid.setCheckable(True)

            if color in self.colors:
                wid.setChecked(True)

            cmd_ = lambda e, c=color: self._clicked.emit(c)
            wid.triggered.connect(cmd_)

            self.addAction(wid)


class RatingMenu(QMenu):
    _clicked = pyqtSignal(int)

    def __init__(self, parent: QMenu, src: str, rating: int):
        super().__init__(parent=parent, title=RATING_T)
        self.src = src
        self.rating = rating

        for rating in range(1, 6):

            wid = QAction(parent=self, text=STAR_SYM * rating)
            wid.setCheckable(True)

            if self.rating == rating:
                wid.setChecked(True)

            cmd_ = lambda e, r=rating: self._clicked.emit(r)
            wid.triggered.connect(cmd_)

            self.addAction(wid)


class TextCut(QAction):
    def __init__(self, parent: QMenu, widget: QLineEdit):
        super().__init__(parent=parent, text=CUT_T)
        self.wid = widget
        self.triggered.connect(self.cmd_)

    def cmd_(self):
        selection = self.wid.selectedText()
        text = self.wid.text().replace(selection, "")
        self.wid.setText(text)
        Utils.write_to_clipboard(selection)


class TextCopy(QAction):
    def __init__(self, parent: QMenu, widget: QLineEdit):
        super().__init__(parent=parent, text=COPY_T)
        self.wid = widget
        self.triggered.connect(self.cmd_)

    def cmd_(self):
        selection = self.wid.selectedText()
        Utils.write_to_clipboard(selection)


class TextPaste(QAction):
    def __init__(self, parent: QMenu, widget: QLineEdit):
        super().__init__(parent=parent, text=PASTE_T)
        self.wid = widget
        self.triggered.connect(self.cmd_)

    def cmd_(self):
        text = Utils.read_from_clipboard()
        new_text = self.wid.text() + text
        self.wid.setText(new_text)


class TextSelectAll(QAction):
    def __init__(self, parent: QMenu, widget: QLineEdit):
        super().__init__(parent=parent, text=SELECT_ALL_T)
        self.wid = widget
        self.triggered.connect(self.cmd_)

    def cmd_(self):
        self.wid.selectAll()


class SortMenu(QMenu):
    def __init__(self, parent: QMenu):
        super().__init__(parent=parent, title=SORT_T)

        asc_cmd = lambda: self.cmd_revers(reversed=False)
        ascen = QAction(parent=self, text=ASCENDING_T)
        ascen.rev = False
        ascen.triggered.connect(asc_cmd)

        desc_cmd = lambda: self.cmd_revers(reversed=True)
        descen = QAction(parent=self, text=DISCENDING_T)
        descen.rev = True
        descen.triggered.connect(desc_cmd)

        for i in (ascen, descen):
            i.setCheckable(True)
            self.addAction(i)

            if i.rev == JsonData.reversed:
                i.setChecked(True)

        self.addSeparator()

        for true_name, dict_ in ORDER.items():
            text_ = dict_.get("text")
            action_ = QAction(parent=self, text=text_)
            action_.setCheckable(True)

            cmd_ = lambda e, s=true_name: self.cmd_sort(sort=s)
            action_.triggered.connect(cmd_)

            if JsonData.sort == true_name:
                action_.setChecked(True)

            self.addAction(action_)

    def cmd_sort(self, sort: str):
        JsonData.sort = sort
        SignalsApp.all_.sort_grid.emit()

    def cmd_revers(self, reversed: bool):
        JsonData.reversed = reversed
        SignalsApp.all_.sort_grid.emit()

class ChangeView(QMenu):
    def __init__(self, parent: QMenu, src: str):
        super().__init__(parent=parent, title=CHANGE_VIEW_T)
        self.src = src

        grid_ = QAction(self, text=CHANGE_VIEW_GRID_T)
        grid_.triggered.connect(self.set_grid)
        grid_.setCheckable(True)
        self.addAction(grid_)

        list_ = QAction(self, text=CHANGE_VIEW_LIST_T)
        list_.triggered.connect(self.set_list)
        list_.setCheckable(True)
        self.addAction(list_)

        if Dynamic.grid_view_type == 0:
            grid_.setChecked(True)
        elif Dynamic.grid_view_type == 1:
            list_.setChecked(True)

    def set_grid(self):
        Dynamic.grid_view_type = 0
        SignalsApp.all_.load_standart_grid.emit("")

    def set_list(self):
        Dynamic.grid_view_type = 1
        SignalsApp.all_.load_standart_grid.emit("")