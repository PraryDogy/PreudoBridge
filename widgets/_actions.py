import subprocess

from PyQt5.QtWidgets import QAction, QMenu

from utils import URunnable, UThreadPool, Utils

from .win_info import WinInfo

REVEAL_T = "Показать в Finder"
INFO_T = "Инфо"
COPY_PATH_T = "Скопировать путь до файла"


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