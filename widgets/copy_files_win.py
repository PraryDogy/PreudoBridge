import os

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (QHBoxLayout, QLabel, QProgressBar, QPushButton,
                             QVBoxLayout, QWidget)

from cfg import Dynamic, Static
from evlosh_templates.evlosh_utils import EvloshUtils
from system.tasks import CopyFilesTask
from system.utils import UThreadPool, Utils

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


class CopyFilesWin(ProgressbarWin):
    finished_ = pyqtSignal(list)
    error_win = pyqtSignal()

    preparing_text = "Подготовка"
    progressbar_width = 300
    icon_size = 50

    def __init__(self, src: str, dest: str, urls: list[str], is_cut: bool):

        if is_cut:
            title_text = "Перемещаю файлы"
        else:
            title_text = "Копирую файлы"

        super().__init__(title_text, Static.COPY_FILES_SVG)

        src_txt = self.limit_string(os.path.basename(src))
        dest_txt = self.limit_string(os.path.basename(dest))
        src_dest_text = f"Из \"{src_txt}\" в \"{dest_txt}\""
        self.above_label.setText(src_dest_text)
        self.below_label.setText(self.preparing_text)
        self.cancel_btn.mouseReleaseEvent = self.cancel_cmd
        self.adjustSize()

        self.tsk = CopyFilesTask(src, dest, urls, is_cut)
        self.tsk.signals_.set_total_kb.connect(lambda value: self.set_max(value))
        self.tsk.signals_.set_copied_kb.connect(lambda value: self.set_value(value))
        self.tsk.signals_.finished_.connect(lambda urls: self.on_finished(urls))
        self.tsk.signals_.error_win.connect(lambda: self.error_win.emit())
        self.tsk.signals_.replace_files_win.connect(lambda: self.open_replace_files_win())
        self.tsk.signals_.set_counter.connect(lambda data: self.set_counter(*data))
        UThreadPool.start(self.tsk)

    def open_replace_files_win(self):

        def continue_copy():
            self.tsk.pause_flag = False

        replace_win = ReplaceFilesWin()
        replace_win.center(self)
        replace_win.ok_pressed.connect(continue_copy)
        replace_win.cancel_pressed.connect(self.cancel_cmd)
        replace_win.show()

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

    def set_counter(self, current: int, total: int):
        try:
            self.below_label.setText(f"Скопировано {current} из {total}")
        except RuntimeError:
            Utils.print_error()

    def cancel_cmd(self, *args):
        self.tsk.pause_flag = False
        self.tsk.set_should_run(False)
        self.deleteLater()

    def on_finished(self, urls: list[str]):
        self.finished_.emit(urls)
        self.deleteLater()
