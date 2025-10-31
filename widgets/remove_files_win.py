from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
                             QWidget)

from cfg import Static
from system.items import MainWinItem
from system.tasks import FileRemover, UThreadPool

from ._base_widgets import MinMaxDisabledWin, USvgSqareWidget


class RemoveFilesWin(MinMaxDisabledWin):
    finished_ = pyqtSignal(list)
    descr_text = "Удалить безвозвратно"
    ok_text = "Ок"
    cancel_text = "Отмена"
    title_text = "Внимание!"
    svg_size = 50

    def __init__(self, main_win_item: MainWinItem, urls: list[str]):
        super().__init__()
        self.setWindowTitle(RemoveFilesWin.title_text)
        self.set_modality()
        self.urls = urls
        self.main_win_item = main_win_item

        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(10, 10, 10, 10)
        self.centralWidget().setLayout(v_lay)

        first_row_wid = QWidget()
        v_lay.addWidget(first_row_wid)
        first_row_lay = QHBoxLayout()
        first_row_lay.setContentsMargins(0, 0, 0, 0)
        first_row_wid.setLayout(first_row_lay)

        warn = USvgSqareWidget(Static.app_icons_dir.get("warning.svg"), RemoveFilesWin.svg_size)
        first_row_lay.addWidget(warn)

        t = f"{RemoveFilesWin.descr_text} ({len(urls)})?"
        question = QLabel(text=t)
        first_row_lay.addWidget(question)

        h_wid = QWidget()
        v_lay.addWidget(h_wid)
        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.setSpacing(10)
        h_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h_wid.setLayout(h_lay)

        ok_btn = QPushButton(RemoveFilesWin.ok_text)
        ok_btn.clicked.connect(self.cmd_)
        ok_btn.setFixedWidth(90)
        h_lay.addWidget(ok_btn)

        can_btn = QPushButton(RemoveFilesWin.cancel_text)
        can_btn.clicked.connect(self.deleteLater)
        can_btn.setFixedWidth(90)
        h_lay.addWidget(can_btn)

        self.adjustSize()

    def cmd_(self, *args):
        self.task_ = FileRemover(self.main_win_item.main_dir, self.urls)
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
    