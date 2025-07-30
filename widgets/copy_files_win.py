import os

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (QHBoxLayout, QLabel, QProgressBar, QPushButton,
                             QVBoxLayout, QWidget)

from cfg import Static, Dynamic
from evlosh_templates.evlosh_utils import EvloshUtils
from system.tasks import CopyFilesTask
from system.utils import UThreadPool, Utils

from ._base_widgets import MinMaxDisabledWin, USvgSqareWidget


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

        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(10, 5, 10, 10)
        main_lay.setSpacing(10)
        self.setLayout(main_lay)

        h_wid = QWidget()
        main_lay.addWidget(h_wid)

        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.setSpacing(10)
        h_wid.setLayout(h_lay)

        warn = USvgSqareWidget(Static.WARNING_SVG, self.icon_size)
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

        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(10, 5, 10, 10)
        main_lay.setSpacing(0)
        self.setLayout(main_lay)

        h_wid = QWidget()
        main_lay.addWidget(h_wid)

        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.setSpacing(10)
        h_wid.setLayout(h_lay)

        warn = USvgSqareWidget(Static.WARNING_SVG, ErrorWin.icon_size)
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


class CopyFilesWin(MinMaxDisabledWin):
    finished_ = pyqtSignal(list)
    error_ = pyqtSignal()

    preparing_text = "Подготовка"
    progressbar_width = 300
    icon_size = 50

    def __init__(self, dest: str, urls: list[str]):
        super().__init__()

        if Dynamic.is_cut:
            title_text = "Перемещаю файлы"
        else:
            title_text = "Копирую файлы"

        self.setWindowTitle(title_text)

        main_lay = QHBoxLayout()
        main_lay.setContentsMargins(10, 10, 10, 10)
        main_lay.setSpacing(5)
        self.setLayout(main_lay)

        left_side_icon = USvgSqareWidget(Static.COPY_FILES_SVG, CopyFilesWin.icon_size)
        main_lay.addWidget(left_side_icon)

        right_side_wid = QWidget()
        right_side_lay = QVBoxLayout()
        right_side_lay.setContentsMargins(0, 0, 0, 0)
        right_side_lay.setSpacing(0)
        right_side_wid.setLayout(right_side_lay)
        main_lay.addWidget(right_side_wid)

        src = min(urls, key=len)
        src = os.path.dirname(EvloshUtils.normalize_slash(src))
        src = os.path.basename(src)
        src = self.limit_string(src)

        dest_ = os.path.basename(dest)
        dest_ = self.limit_string(dest_)

        src_dest_lbl = QLabel(self.set_text(src, dest_))
        right_side_lay.addWidget(src_dest_lbl)

        progressbar_row = QWidget()
        right_side_lay.addWidget(progressbar_row)
        progressbar_lay = QHBoxLayout()
        progressbar_lay.setContentsMargins(0, 0, 0, 0)
        progressbar_lay.setSpacing(10)
        progressbar_row.setLayout(progressbar_lay)

        self.progressbar = QProgressBar()
        self.progressbar.setTextVisible(False)
        self.progressbar.setFixedHeight(6)
        self.progressbar.setFixedWidth(CopyFilesWin.progressbar_width)
        progressbar_lay.addWidget(self.progressbar)

        cancel_btn = USvgSqareWidget(Static.CLEAR_SVG, 16)
        cancel_btn.mouseReleaseEvent = self.cancel_cmd
        progressbar_lay.addWidget(cancel_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.size_mb_lbl = QLabel(CopyFilesWin.preparing_text)
        right_side_lay.addWidget(self.size_mb_lbl)

        self.adjustSize()

        if urls:
            task_ = CopyFilesTask(dest, urls)
            task_.signals_.set_max.connect(lambda value: self.set_max(value))
            task_.signals_.set_value.connect(lambda value: self.set_value(value))
            task_.signals_.set_size_mb.connect(lambda text: self.size_mb_text(text))
            task_.signals_.finished_.connect(lambda urls: self.on_finished(urls))
            task_.signals_.error_.connect(lambda: self.open_replace_files_win())
            task_.signals_.replace_files.connect(lambda: self.open_replace_files_win(task_))
            UThreadPool.start(task_)

    def open_replace_files_win(self, task: CopyFilesTask):
        replace_win = ReplaceFilesWin()
        replace_win.center(self)
        replace_win.ok_pressed.connect(lambda: self.continue_copy(task))
        replace_win.cancel_pressed.connect(lambda: self.cancel_copy(task))
        replace_win.show()

    def continue_copy(self, task: CopyFilesTask):
        task.pause_flag = False

    def cancel_copy(self, task: CopyFilesTask):
        task.pause_flag = False
        task.cancel_flag = True

    def size_mb_text(self, text: str):
        self.size_mb_lbl.setText(text)

    def set_text(self, src: str, dest: str):
        return f"Из \"{src}\" в \"{dest}\""

    def limit_string(self, text: str, limit: int = 15):
        if len(text) > limit:
            return text[:limit] + "..."
        return text

    def set_max(self, value):
        try:
            self.progressbar.setMaximum(abs(value))
        except RuntimeError as e:
            Utils.print_error()

    def set_value(self, value):
        try:
            self.progressbar.setValue(value)
        except RuntimeError as e:
            Utils.print_error()

    def cancel_cmd(self, *args):
        self.deleteLater()

    def on_finished(self, urls: list[str]):
        self.finished_.emit(urls)
        self.deleteLater()
