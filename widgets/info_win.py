import os

from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QContextMenuEvent, QKeyEvent
from PyQt5.QtWidgets import QAction, QGridLayout, QLabel

from cfg import Static
from utils import URunnable, UThreadPool, Utils

from ._base_widgets import BaseItem, UMenu, MinMaxDisabledWin
from .actions import CopyText, RevealInFinder

CALCULATING = "Вычисляю..."
TITLE = "Инфо"
NAME_T = "Имя"
TYPE_T = "Тип"
SIZE_T = "Размер"
SRC_T = "Место"
BITRTH_T = "Создан"
MOD_T = "Изменен"
RESOL_T = "Разрешение"
UNDEFINED = "Неизвестно"
MAX_ROW = 50
SELECT_ALL_T = "Выделить все"

class WorkerSignals(QObject):
    finished_ = pyqtSignal(str)


class CalculatingTask(URunnable):
    def __init__(self, base_item: BaseItem):
        super().__init__()
        self.base_item = base_item
        self.signals_ = WorkerSignals()

    @URunnable.set_running_state
    def run(self):
        try:
            if self.base_item.type_ == Static.FOLDER_TYPE:
                res = self.get_folder_size()
            else:
                res = self.get_img_resol()

            self.signals_.finished_.emit(res)

        except Exception as e:
            Utils.print_error(parent=None, error=e)

    def get_img_resol(self):
        img_ = Utils.read_image(path=self.base_item.src)

        if img_ is not None and len(img_.shape) > 1:
            h, w = img_.shape[0], img_.shape[1]
            resol= f"{w}x{h}"
        else:
            resol = UNDEFINED

        return resol

    def get_folder_size(self):
        total = 0
        stack = []
        stack.append(self.base_item.src)

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
            return total


class InfoTask:
    def __init__(self, base_item: BaseItem):
        super().__init__()
        self.base_item = base_item

    def get(self) -> dict[str, str| int]:
        size_ = (
            Utils.get_f_size(os.path.getsize(self.base_item.src))
            if self.base_item.type_ != Static.FOLDER_TYPE
            else
            CALCULATING
            )

        res = {
            NAME_T: self.lined_text(os.path.basename(self.base_item.src)),
            TYPE_T: self.base_item.type_,
            MOD_T: Utils.get_f_date(os.stat(self.base_item.src).st_mtime),
            SRC_T: self.lined_text(self.base_item.src),
            SIZE_T: size_,
            }
        
        if self.base_item.type_ != Static.FOLDER_TYPE:
            res.update(
                {RESOL_T: CALCULATING}
            )

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


class SelectableLabel(QLabel):
    def __init__(self, text: str = None):
        super().__init__(text)

    def select_all_cmd(self, *args):
        self.setSelection(0, len(self.text()))

    def contextMenuEvent(self, ev: QContextMenuEvent | None) -> None:

        src = self.text().replace(Static.PARAGRAPH_SEP, "")
        src = src.replace(Static.LINE_FEED, "")

        menu = UMenu(self)

        copy_action = CopyText(parent=menu, widget=self)
        menu.addAction(copy_action)

        select_all_act = QAction(SELECT_ALL_T, menu)
        select_all_act.triggered.connect(self.select_all_cmd)
        menu.addAction(select_all_act)

        if os.path.exists(src):
            menu.addSeparator()

            reveal_action = RevealInFinder(menu, src)
            menu.addAction(reveal_action)

        menu.exec_(ev.globalPos())


class InfoWin(MinMaxDisabledWin):
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
        base_item = BaseItem(self.src, 0)
        base_item.set_src()
        base_item.set_name()
        base_item.set_file_type()
        base_item.set_stat()
        info_ = InfoTask(base_item)
        info_ = info_.get()

        for name, value in info_.items():

            left_lbl = SelectableLabel(name)
            flags_l_al = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
            self.grid_layout.addWidget(left_lbl, row, 0, alignment=flags_l_al)

            right_lbl = SelectableLabel(value)
            flags_r = Qt.TextInteractionFlag.TextSelectableByMouse
            right_lbl.setTextInteractionFlags(flags_r)
            flags_r_al = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom
            self.grid_layout.addWidget(right_lbl, row, 1, alignment=flags_r_al)

            row += 1

        self.adjustSize()
        self.setFixedSize(self.width(), self.height())

        cmd_ = lambda result: self.finalize(result=result)
        self.task_ = CalculatingTask(base_item=base_item)
        self.task_.signals_.finished_.connect(cmd_)
        UThreadPool.start(runnable=self.task_)

    def finalize(self, result: str):
        # лейбл с динамической переменной у нас всегда самый последний в
        # списке виджетов
        # то есть разрешение фотографии или размер папки
        # смотри InfoTask - как формируется результат
        label = self.findChildren(SelectableLabel)[-1]
        left_label = self.findChildren(SelectableLabel)[-2]
        label.setText(result)

        if result == UNDEFINED:
            for i in (label, left_label):
                i.setText("")

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Return):
            self.close()

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        if hasattr(self, "task_"):
            self.task_.should_run = False
        return super().closeEvent(a0)