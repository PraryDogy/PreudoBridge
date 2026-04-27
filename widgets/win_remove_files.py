import os

from PyQt5.QtCore import Qt, pyqtSignal

from system.items import MainWinItem

from .win_warn import ConfirmWindow


class WinRemoveFiles(ConfirmWindow):
    ok_clicked = pyqtSignal()
    remove_perm = "Удалить безвозвратно"
    move_to_trash = "Переместить в корзину"

    def __init__(self, path: str, main_win_item: MainWinItem):
        if path.startswith(os.path.expanduser("~")):
            t = f"{WinRemoveFiles.move_to_trash}?"
        else:
            t = f"{WinRemoveFiles.remove_perm}?"

        super().__init__(text=t)
        self.setFixedSize(270, 100)
