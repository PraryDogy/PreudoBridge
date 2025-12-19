import gc
import os

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (QHBoxLayout, QLabel, QProgressBar, QPushButton,
                             QVBoxLayout, QWidget)

from cfg import Static
from system.items import CopyItem
from system.tasks import CopyFilesTask, UThreadPool

from ._base_widgets import MinMaxDisabledWin, USvgSqareWidget
from .progressbar_win import ProgressbarWin


class ReplaceFilesWin(MinMaxDisabledWin):
    descr_text = "Заменить существующие файлы?"
    title_text = "Замена"
    ok_text = "Ок"
    cancel_text = "Отмена"
    icon_size = 50

    ok_pressed = pyqtSignal()
    cancel_pressed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.set_modality()
        self.setWindowTitle(self.title_text)

        main_lay = QVBoxLayout()
        main_lay.setContentsMargins(10, 5, 10, 10)
        main_lay.setSpacing(10)
        self.centralWidget().setLayout(main_lay)

        h_wid = QWidget()
        main_lay.addWidget(h_wid)

        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.setSpacing(10)
        h_wid.setLayout(h_lay)

        warn = USvgSqareWidget(os.path.join(Static.internal_icons_dir, "warning.svg"), self.icon_size)
        h_lay.addWidget(warn)

        test_two = QLabel(self.descr_text)
        test_two.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        h_lay.addWidget(test_two)

        btn_wid = QWidget()
        main_lay.addWidget(btn_wid)

        btn_lay = QHBoxLayout()
        btn_lay.setContentsMargins(0, 0, 0, 0)
        btn_lay.setSpacing(10)
        btn_wid.setLayout(btn_lay)

        btn_lay.addStretch()

        ok_btn = QPushButton(self.ok_text)
        ok_btn.setFixedWidth(90)
        ok_btn.clicked.connect(lambda: self.ok_cmd())
        btn_lay.addWidget(ok_btn)

        cancel_btn = QPushButton(self.cancel_text)
        cancel_btn.setFixedWidth(90)
        cancel_btn.clicked.connect(lambda: self.cancel_cmd())
        btn_lay.addWidget(cancel_btn)
        
        btn_lay.addStretch()
        self.adjustSize()

    def ok_cmd(self):
        self.ok_pressed.emit()
        self.deleteLater()

    def cancel_cmd(self):
        self.cancel_pressed.emit()
        self.deleteLater()

    def closeEvent(self, a0):
        self.deleteLater()
        a0.ignore()        
    

class ErrorWin(MinMaxDisabledWin):
    descr_text = "Произошла ошибка при копировании"
    title_text = "Ошибка"
    ok_text = "Ок"
    icon_size = 50

    def __init__(self):
        super().__init__()
        self.set_modality()
        self.setWindowTitle(ErrorWin.title_text)

        main_lay = QVBoxLayout()
        main_lay.setContentsMargins(10, 5, 10, 10)
        main_lay.setSpacing(0)
        self.centralWidget().setLayout(main_lay)

        h_wid = QWidget()
        main_lay.addWidget(h_wid)

        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.setSpacing(10)
        h_wid.setLayout(h_lay)

        warn = USvgSqareWidget(os.path.join(Static.internal_icons_dir, "warning.svg"), ErrorWin.icon_size)
        h_lay.addWidget(warn)

        test_two = QLabel(ErrorWin.descr_text)
        test_two.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        h_lay.addWidget(test_two)

        ok_btn = QPushButton(ErrorWin.ok_text)
        ok_btn.clicked.connect(self.deleteLater)
        ok_btn.setFixedWidth(90)
        main_lay.addWidget(ok_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.adjustSize()

    def keyPressEvent(self, a0):
        if a0.key() == Qt.Key.Key_Escape:
            self.deleteLater()
        elif a0.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
            self.deleteLater()
        elif a0.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if a0.key() == Qt.Key.Key_Q:
                return
        return super().keyPressEvent(a0)


class CopyFilesWin(ProgressbarWin):
    finished_ = pyqtSignal(list)
    error_win = pyqtSignal()

    preparing_text = "Подготовка"
    progressbar_width = 300
    icon_size = 50

    def __init__(self):

        if CopyItem.get_is_cut():
            title_text = "Перемещаю файлы"
        else:
            title_text = "Копирую файлы"

        super().__init__(title_text, os.path.join(Static.internal_icons_dir, "files.svg"))

        src_txt = self.limit_string(os.path.basename(CopyItem.get_src()))
        dest_txt = self.limit_string(os.path.basename(CopyItem.get_dest()))
        src_dest_text = f"Из \"{src_txt}\" в \"{dest_txt}\""
        self.above_label.setText(src_dest_text)
        self.below_label.setText(self.preparing_text)
        self.cancel_btn.clicked.connect(self.cancel_cmd)
        self.adjustSize()

        self.tsk = CopyFilesTask()
        self.tsk.sigs.total_size.connect(self.progressbar.setMaximum)
        self.tsk.sigs.finished_.connect(lambda urls: self.on_finished(urls))
        self.tsk.sigs.error_win.connect(lambda: self.error_win.emit())
        self.tsk.sigs.replace_files_win.connect(lambda: self.open_replace_files_win())

        UThreadPool.start(self.tsk)

        self.timer_ = QTimer(self)
        self.timer_.timeout.connect(self.update_gui)
        self.timer_.start(1000)

    def update_gui(self):
        self.progressbar.setValue(self.tsk.copied_size)
        if CopyItem.get_is_cut():
            copy = "Перемещаю файлы"
        else:
            copy = "Копирую файлы"
        self.below_label.setText(f"{copy} {self.tsk.copied_count} из {self.tsk.total_count}")

    def open_replace_files_win(self):
        replace_win = ReplaceFilesWin()
        replace_win.center(self)
        replace_win.ok_pressed.connect(lambda: self.tsk.toggle_pause_flag(False))
        replace_win.cancel_pressed.connect(self.cancel_cmd)
        replace_win.show()

    def limit_string(self, text: str, limit: int = 15):
        if len(text) > limit:
            return text[:limit] + "..."
        return text

    def cancel_cmd(self, *args):
        self.timer_.stop()
        self.tsk.set_should_run(False)
        self.deleteLater()

    def on_finished(self, urls: list[str]):
        self.timer_.stop()
        self.finished_.emit(urls)
        self.deleteLater()
