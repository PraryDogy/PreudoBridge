import subprocess

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QAction, QMenu

from cfg import COLORS, IMAGE_APPS, STAR_SYM
from utils import URunnable, UThreadPool, Utils

from .win_info import WinInfo

REVEAL_T = "Показать в Finder"
INFO_T = "Инфо"
COPY_PATH_T = "Скопировать путь"
VIEW_T = "Просмотр"
OPEN_IN_APP_T = "Открыть в приложении"
COLORS_T = "Цвета"
RATING_T = "Рейтинг"
SHOW_IN_FOLDER_T = "Показать в папке"
FAV_REMOVE_T = "Удалить из избранного"
FAV_ADD_T = "Добавить в избранное"


class Task_(URunnable):
    def __init__(self,  cmd_: callable):
        super().__init__()
        self.cmd_ = cmd_

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
        self.win_info = WinInfo(self.src)
        Utils.center_win(parent=Utils.get_main_win(), child=self.win_info)
        self.win_info.show()


class CopyPath(UAction):
    def __init__(self, parent: QMenu, src: str):
        super().__init__(parent, src, COPY_PATH_T)

    def cmd_(self):
        Utils.copy_path(self.src)


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


class FavAdd(UAction):
    _clicked = pyqtSignal()

    def __init__(self, parent: QMenu, src: str):
        super().__init__(parent, src, FAV_ADD_T)

    def cmd_(self):
        self._clicked.emit()


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