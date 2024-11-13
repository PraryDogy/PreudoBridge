import os

from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QContextMenuEvent, QKeyEvent
from PyQt5.QtWidgets import QApplication, QGridLayout, QLabel, QMenu

from cfg import FOLDER_TYPE
from utils import URunnable, UThreadPool, Utils

from ._base import WinMinMax

CALCULATING = "Вычисляю..."
NAMES = ["Имя", "Тип", "Размер", "Место", "Создан", "Изменен"]
TITLE = "Инфо"


class WorkerSignals(QObject):
    _finished = pyqtSignal(str)


class FolderSize(URunnable):
    def __init__(self, src: str):
        super().__init__()
        self.src = src
        self.worker_signals = WorkerSignals()

    @URunnable.set_running_state
    def run(self):
        total = 0

        for root, _, files in os.walk(self.src):

            if not self.should_run:
                return

            for file in files:

                if not self.should_run:
                    return

                src_ = os.path.join(root, file)

                try:
                    size_ = os.path.getsize(src_)
                    total += size_
                except Exception as e:
                    # Utils.print_error(parent=self, error=e)
                    continue

        total = Utils.get_f_size(total)

        if self.should_run:
            self.worker_signals._finished.emit(total)


class InfoTask:
    def __init__(self, src: str):
        super().__init__()
        self.src = src

    def get(self):
        is_file = os.path.isfile(self.src)

        name = self.lined_text(os.path.basename(self.src))
        type_ = (
            os.path.splitext(self.src)[-1]
            if is_file
            else
            FOLDER_TYPE
            )
        size_ = (
            Utils.get_f_size(os.path.getsize(self.src))
            if is_file
            else
            CALCULATING
            )
        src = self.lined_text(self.src)
        stats = os.stat(self.src)
        birth = Utils.get_f_date(stats.st_birthtime)
        mod = Utils.get_f_date(stats.st_mtime)

        return (name, type_, size_, src, birth, mod)

    def lined_text(self, text: str):
        max_row = 38

        if len(text) > max_row:
            text = [
                text[i:i + max_row]
                for i in range(0, len(text), max_row)
                ]
            return "\n".join(text)
        else:
            return text 


class CustomLabel(QLabel):
    def __init__(self, text: str = None):
        super().__init__(text)

    def contextMenuEvent(self, ev: QContextMenuEvent | None) -> None:
        self.setSelection(0, len(self.text()))
        menu = QMenu(self)
        copy_action = menu.addAction("Копировать")
        copy_action.triggered.connect(self.custom_copy)
        menu.exec_(ev.globalPos())

    def custom_copy(self):
        modified_text = self.text().replace("\n", "")
        clipboard = QApplication.clipboard()
        clipboard.setText(modified_text)


class WinInfo(WinMinMax):
    def __init__(self, src: str):
        super().__init__()
        self.setWindowTitle(TITLE)

        self.src = src

        self.grid_layout = QGridLayout()
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)
        self.grid_layout.setSpacing(5)
        self.setLayout(self.grid_layout)

        row = 0

        task_ = InfoTask(self.src)
        info = task_.get()

        for name, text in zip(NAMES, info):

            left_lbl = CustomLabel(name)
            flags_l_al = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
            self.grid_layout.addWidget(left_lbl, row, 0, alignment=flags_l_al)

            right_lbl = CustomLabel(text)
            flags_r = Qt.TextInteractionFlag.TextSelectableByMouse
            right_lbl.setTextInteractionFlags(flags_r)
            flags_r_al = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom
            self.grid_layout.addWidget(right_lbl, row, 1, alignment=flags_r_al)

            if text == CALCULATING:
                setattr(self, "calc", True)
                setattr(self, "size_label", right_lbl)

            row += 1

        w = 350
        self.adjustSize()
        self.setMinimumWidth(w)
        self.setFixedHeight(self.height())
        self.resize(self.height(), w)
   
        if hasattr(self, "calc"):
            cmd_ = lambda size_: self.finalize(size_)
            self.task_ = FolderSize(self.src)
            self.task_.worker_signals._finished.connect(cmd_)
            UThreadPool.pool.start(self.task_)

    def finalize(self, size_: str):
        label: CustomLabel = getattr(self, "size_label")
        label.setText(size_)

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Return):
            self.close()

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        if hasattr(self, "task_"):
            self.task_.should_run = False
        return super().closeEvent(a0)