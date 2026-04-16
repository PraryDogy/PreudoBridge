from PyQt5.QtCore import Qt, QTimer, pyqtSignal

from cfg import Dynamic
from system.items import MainWinItem
from system.tasks import FileRemover, UThreadPool

from .warn_win import ConfirmWindow


class WinRemoveFiles(ConfirmWindow):
    finished_ = pyqtSignal(list)
    remove_perm = "Удалить безвозвратно"
    move_to_trash = "Переместить в корзину"

    def __init__(self, main_win_item: MainWinItem, urls: list[str]):
        if "uuid" in main_win_item.fs_id:
            t = f"{WinRemoveFiles.move_to_trash}?"
        else:
            t = f"{WinRemoveFiles.remove_perm}?"

        super().__init__(text=t)
        self.setFixedSize(270, 100)
        self.urls = urls
        self.main_win_item = main_win_item

        self.ok_btn.clicked.connect(self.cmd_)
        self.cancel_btn.clicked.connect(self.deleteLater)

    def cmd_(self, *args):
        self.hide()
        self.task_ = FileRemover(self.main_win_item.abs_current_dir, self.urls)
        self.task_.sigs.finished_.connect(self.finalize)
        QTimer.singleShot(100, lambda: UThreadPool.start(runnable=self.task_))

    def finalize(self, *args):
        self.finished_.emit(self.urls)
        del self.task_
        self.deleteLater()

    def keyPressEvent(self, a0):
        if a0.key() == Qt.Key.Key_Escape:
            self.deleteLater()
        elif a0.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
            self.cmd_()
        return super().keyPressEvent(a0)
    