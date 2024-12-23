import os

import sqlalchemy
from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QContextMenuEvent, QKeyEvent
from PyQt5.QtWidgets import QGridLayout, QLabel

from cfg import JsonData, Static
from database import CACHE, Dbase
from utils import URunnable, UThreadPool, Utils

from ._actions import CopyText, RevealInFinder
from ._base import UMenu, WinMinMax

CALCULATING = "Вычисляю..."
TITLE = "Инфо"
NAME_T = "Имя"
TYPE_T = "Тип"
SIZE_T = "Размер"
SRC_T = "Место"
BITRTH_T = "Создан"
MOD_T = "Изменен"
RESOL_T = "Разрешение"

MAX_ROW = 50


class WorkerSignals(QObject):
    finished_ = pyqtSignal(str)


class FolderSize(URunnable):
    def __init__(self, src: str):
        super().__init__()
        self.src = src
        self.signals_ = WorkerSignals()

    @URunnable.set_running_state
    def run(self):
        try:
            self.main()
        except RuntimeError as e:
            Utils.print_error(parent=None, error=e)

    def main(self):
        total = 0
        stack = []
        stack.append(self.src)

        while stack:
            current_dir = stack.pop()

            with os.scandir(current_dir) as entries:

                for entry in entries:

                    if not self.should_run:
                        return

                    if entry.is_dir():
                        stack.append(entry.path)

                    else:
                        try:
                            total += entry.stat().st_size
                        except Exception:
                            ...

        total = Utils.get_f_size(total)

        if self.should_run:
            self.signals_.finished_.emit(total)


class InfoTask:
    def __init__(self, src: str):
        super().__init__()
        self.src = os.sep + src.strip(os.sep)
        self.name = os.path.basename(self.src)


    def get(self) -> dict[str, str| int]:
        db = os.path.join(JsonData.root, Static.DB_FILENAME)
        dbase = Dbase()
        engine = dbase.create_engine(path=db)
        conn = engine.connect()

        cols = (
            CACHE.c.name,
            CACHE.c.type_,
            CACHE.c.mod,
            CACHE.c.resol
            )

        q = sqlalchemy.select(*cols).where(CACHE.c.name==self.name)
        res = conn.execute(q).first()

        conn.close()

        if res:
            return self.get_db_info(*res)

        else:
            return self.get_raw_info()

    def get_db_info(self, name, type_, mod, resol):

        res = {
            NAME_T: self.lined_text(text=name),
            TYPE_T: type_,
            SIZE_T: Utils.get_f_size(os.path.getsize(self.src)),
            MOD_T: Utils.get_f_date(mod),
            RESOL_T: resol,
            SRC_T: self.lined_text(text=self.src)
            }

        return res


    def get_raw_info(self):
        is_file = os.path.isfile(self.src)

        type_ = (
            os.path.splitext(self.src)[-1]
            if is_file
            else
            Static.FOLDER_TYPE
            )

        size_ = (
            Utils.get_f_size(os.path.getsize(self.src))
            if is_file
            else
            CALCULATING
            )

        res = {
            NAME_T: self.lined_text(os.path.basename(self.src)),
            TYPE_T: type_,
            SIZE_T: size_,
            SRC_T: self.lined_text(self.src),
            MOD_T: Utils.get_f_date(os.stat(self.src).st_mtime),
            }

        return res

    def lined_text(self, text: str):
        if len(text) > MAX_ROW:
            text = [
                text[i:i + MAX_ROW]
                for i in range(0, len(text), MAX_ROW)
                ]
            return "\n".join(text)
        else:
            return text


class CustomLabel(QLabel):
    def __init__(self, text: str = None):
        super().__init__(text)

    def contextMenuEvent(self, ev: QContextMenuEvent | None) -> None:

        self.setSelection(0, len(self.text()))
        src = self.selectedText().replace(Static.PARAGRAPH_SEP, "")
        src = src.replace(Static.LINE_FEED, "")

        menu = UMenu(self)

        copy_action = CopyText(parent=menu, widget=self)
        menu.addAction(copy_action)

        menu.addSeparator()

        reveal_action = RevealInFinder(
            parent=menu,
            src=src
        )
        menu.addAction(reveal_action)

        if not os.path.exists(src):
            reveal_action.setDisabled(True)

        menu.exec_(ev.globalPos())

        self.setSelection(0, 0)


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

        for name, value in info.items():

            left_lbl = CustomLabel(name)
            flags_l_al = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
            self.grid_layout.addWidget(left_lbl, row, 0, alignment=flags_l_al)

            right_lbl = CustomLabel(value)
            flags_r = Qt.TextInteractionFlag.TextSelectableByMouse
            right_lbl.setTextInteractionFlags(flags_r)
            flags_r_al = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom
            self.grid_layout.addWidget(right_lbl, row, 1, alignment=flags_r_al)

            if value == CALCULATING:
                setattr(self, "calc", True)
                setattr(self, "size_label", right_lbl)

            row += 1

        self.adjustSize()
        self.setFixedSize(self.width(), self.height())
   
        if hasattr(self, "calc"):
            cmd_ = lambda size_: self.finalize(size_)
            self.task_ = FolderSize(self.src)
            self.task_.signals_.finished_.connect(cmd_)
            UThreadPool.start(self.task_)

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