import subprocess

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QAction, QMenu

from cfg import IMAGE_APPS
from utils import URunnable, UThreadPool, Utils

from .win_info import WinInfo

REVEAL_T = "Показать в Finder"
INFO_T = "Инфо"
COPY_PATH_T = "Скопировать путь до файла"
VIEW_T = "Просмотр"
OPEN_IN_APP_T = "Открыть в приложении"

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


class Reveal(UAction):
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