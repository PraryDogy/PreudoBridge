import os

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
                             QWidget)

from cfg import Static
from system.items import CopyItem
from system.multiprocess import CopyFilesTask, CopyFilesWorker

from ._base_widgets import MinMaxDisabledWin, USvgSqareWidget
from .progressbar_win import ProgressbarWin


class ReplaceFilesWin(MinMaxDisabledWin):
    descr_text = "Заменить существующие файлы?"
    title_text = "Замена"
    replace_one_text = "Заменить"
    replace_all_text = "Заменить все"
    stop_text = "Стоп"
    icon_size = 50

    replace_one_press = pyqtSignal()
    replace_all_press = pyqtSignal()
    stop_pressed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.set_modality()
        self.setWindowTitle(self.title_text)
        self.setFixedSize(400, 100)

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
        main_lay.addWidget(btn_wid, alignment=Qt.AlignmentFlag.AlignRight)

        btn_lay = QHBoxLayout()
        btn_lay.setContentsMargins(0, 0, 0, 0)
        btn_lay.setSpacing(10)
        btn_wid.setLayout(btn_lay)

        btn_lay.addStretch()

        replace_all_btn = QPushButton(self.replace_all_text)
        replace_all_btn.setFixedWidth(95)
        replace_all_btn.clicked.connect(lambda: self.replace_all_cmd())
        btn_lay.addWidget(replace_all_btn)

        replace_one_btn = QPushButton(self.replace_one_text)
        replace_one_btn.setFixedWidth(95)
        replace_one_btn.clicked.connect(lambda: self.replace_one_cmd())
        btn_lay.addWidget(replace_one_btn)

        stop_btn = QPushButton(self.stop_text)
        stop_btn.setFixedWidth(95)
        stop_btn.clicked.connect(lambda: self.stop_cmd())
        btn_lay.addWidget(stop_btn)
        
        btn_lay.addStretch()
        self.adjustSize()

    def replace_one_cmd(self):
        self.replace_one_press.emit()

    def replace_all_cmd(self):
        self.replace_all_press.emit()

    def stop_cmd(self):
        self.stop_pressed.emit()

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
    finished_ = pyqtSignal()
    preparing_text = "Подготовка"
    progressbar_width = 300
    icon_size = 50

    def __init__(self):

        if CopyItem.is_cut:
            title_text = "Перемещаю файлы"
        else:
            title_text = "Копирую файлы"

        super().__init__(title_text, os.path.join(Static.internal_icons_dir, "files.svg"))

        src_txt = self.limit_string(os.path.basename(CopyItem.src_dir))
        dest_txt = self.limit_string(os.path.basename(CopyItem.dst_dir))
        src_dest_text = f"Из \"{src_txt}\" в \"{dest_txt}\""
        self.above_label.setText(src_dest_text)
        self.below_label.setText(self.preparing_text)
        self.progressbar.setMaximum(0)
        self.cancel_btn.clicked.connect(self.deleteLater)
        self.adjustSize()

        data = {
            "src_dir": CopyItem.src_dir,
            "dst_dir": CopyItem.dst_dir,
            "urls": CopyItem.urls,
            "is_search": CopyItem.is_search,
            "is_cut": CopyItem.is_cut,
            "msg": ""
            }

        self.copy_task = CopyFilesWorker(
            target=CopyFilesTask.start,
            args=(data, )
        )
        self.copy_task.start()
        QTimer.singleShot(100, self.poll_task)

    def poll_task(self):
        if not self.copy_task.proc_q.empty():
            result: dict = self.copy_task.proc_q.get()

            if result["msg"] == "error":
                self.error_win = ErrorWin()
                self.error_win.center(self.window())
                self.error_win.show()
                self.deleteLater()
                return
            
            elif result["msg"] == "replace":
                self.replace_win = ReplaceFilesWin()
                self.replace_win.center(self)
                self.replace_win.replace_all_press.connect(self.replace_all)
                self.replace_win.replace_one_press.connect(self.replace_one)
                self.replace_win.stop_pressed.connect(self.deleteLater)
                self.replace_win.show()
                return
            
            if self.progressbar.maximum() == 0:
                self.progressbar.setMaximum(result["total_size"])
            self.progressbar.setValue(result["current_size"])
            if CopyItem.is_cut:
                copy = "Перемещаю файлы"
            else:
                copy = "Копирую файлы"
            self.below_label.setText(
                f'{copy} {result["current_count"]} из {result["total_count"]}'
            )

        if not self.copy_task.proc.is_alive():
            self.finished_.emit()
            self.deleteLater()
        else:
            QTimer.singleShot(100, self.poll_task)

    def limit_string(self, text: str, limit: int = 30):
        if len(text) > limit:
            return text[:limit] + "..."
        return text
    
    def replace_one(self):
        data = {"msg": "replace_one"}
        self.copy_task.gui_q.put(data)
        self.replace_win.deleteLater()
        QTimer.singleShot(100, self.poll_task)

    def replace_all(self):
        data = {"msg": "replace_all"}
        self.copy_task.gui_q.put(data)
        self.replace_win.deleteLater()
        QTimer.singleShot(100, self.poll_task)

    def deleteLater(self):
        self.copy_task.terminate()
        CopyItem.reset()
        # super().deleteLater()