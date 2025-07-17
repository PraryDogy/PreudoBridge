import os

from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtGui import QContextMenuEvent, QKeyEvent
from PyQt5.QtWidgets import QAction, QGridLayout, QLabel

from cfg import Static
from system.utils import ReadImage, Utils

from ._base_items import (BaseItem, MinMaxDisabledWin, UMenu, URunnable,
                          UThreadPool)
from .actions import CopyText, RevealInFinder

UNDEFINED = "Неизвестно"

class WorkerSignals(QObject):
    finished_ = pyqtSignal(str)


class CalculatingTask(URunnable):
    def __init__(self, base_item: BaseItem):
        super().__init__()
        self.base_item = base_item
        self.signals_ = WorkerSignals()

    def task(self):
        try:
            if self.base_item.type_ == Static.FOLDER_TYPE:
                res = self.get_folder_size()
            else:
                res = self.get_img_resol()
        except Exception as e:
            Utils.print_error()
            res = "Ошибка"
        try:
            self.signals_.finished_.emit(res)
        except RuntimeError as e:
            Utils.print_error()

    def get_img_resol(self):
        img_ = ReadImage.read_image(self.base_item.src)
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
                    if entry.is_dir():
                        stack.append(entry.path)
                    else:
                        total += entry.stat().st_size
        total = Utils.get_f_size(total)
        return total


class InfoTask:
    ru = "Папка"
    calculating = "Вычисляю..."
    name_text = "Имя"
    type_text = "Тип"
    size_text = "Размер"
    src_text = "Место"
    mod_text = "Изменен"
    res_text = "Разрешение"
    row_limit = 50

    def __init__(self, base_item: BaseItem):
        super().__init__()
        self.base_item = base_item

    def get(self) -> dict[str, str| int]:
        size_ = (
            Utils.get_f_size(os.path.getsize(self.base_item.src))
            if self.base_item.type_ != Static.FOLDER_TYPE
            else
            InfoTask.calculating
            )
        
        type_t_ = (
            self.base_item.type_
            if self.base_item.type_ != Static.FOLDER_TYPE
            else InfoTask.ru
        )

        res = {
            InfoTask.name_text: self.lined_text(os.path.basename(self.base_item.src)),
            InfoTask.type_text: type_t_,
            InfoTask.mod_text: Utils.get_f_date(os.stat(self.base_item.src).st_mtime),
            InfoTask.src_text: self.lined_text(self.base_item.src),
            InfoTask.size_text: size_,
            }
        
        if self.base_item.type_ != Static.FOLDER_TYPE:
            res.update({InfoTask.res_text: InfoTask.calculating})

        return res

    def lined_text(self, text: str):
        if len(text) > InfoTask.row_limit:
            text = [
                text[i:i + InfoTask.row_limit]
                for i in range(0, len(text), InfoTask.row_limit)
                ]
            return "\n".join(text)
        else:
            return text


class SelectableLabel(QLabel):
    select_all_text = "Выделить все"

    def __init__(self, text: str = None):
        super().__init__(text)
        flags = Qt.TextInteractionFlag.TextSelectableByMouse
        self.setTextInteractionFlags(flags)

    def select_all_cmd(self, *args):
        self.setSelection(0, len(self.text()))

    def contextMenuEvent(self, ev: QContextMenuEvent | None) -> None:

        src = self.text().replace(Static.PARAGRAPH_SEP, "")
        src = src.replace(Static.LINE_FEED, "")

        menu = UMenu(parent=self)

        copy_action = CopyText(menu, self)
        menu.addAction(copy_action)

        select_all_act = QAction(SelectableLabel.select_all_text, menu)
        select_all_act.triggered.connect(self.select_all_cmd)
        menu.addAction(select_all_act)

        if os.path.exists(src):
            menu.addSeparator()

            reveal_action = RevealInFinder(menu, src)
            menu.addAction(reveal_action)

        menu.exec_(ev.globalPos())


class InfoWin(MinMaxDisabledWin):
    title_text = "Инфо"

    def __init__(self, src: str):
        super().__init__()
        self.setWindowTitle(InfoWin.title_text)
        self.set_modality()

        self.src = src

        self.grid_layout = QGridLayout()
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)
        self.grid_layout.setSpacing(5)
        self.setLayout(self.grid_layout)

        row = 0
        base_item = BaseItem(self.src)
        base_item.setup_attrs()
        info_ = InfoTask(base_item)
        info_ = info_.get()

        for name, value in info_.items():

            left_lbl = SelectableLabel(name)
            flags_l_al = Qt.AlignmentFlag.AlignRight
            self.grid_layout.addWidget(left_lbl, row, 0, alignment=flags_l_al)

            right_lbl = SelectableLabel(value)
            flags_r_al = Qt.AlignmentFlag.AlignLeft
            self.grid_layout.addWidget(right_lbl, row, 1, alignment=flags_r_al)

            row += 1

        self.adjustSize()

        cmd_ = lambda result: self.finalize(result)
        task_ = CalculatingTask(base_item)
        task_.signals_.finished_.connect(cmd_)
        UThreadPool.start(task_)

    def finalize(self, result: str):
        # лейбл с динамической переменной у нас всегда самый последний в
        # списке виджетов
        # то есть разрешение фотографии или размер папки
        # смотри InfoTask - как формируется результат
        label = self.findChildren(SelectableLabel)[-1]
        left_label = self.findChildren(SelectableLabel)[-2]
        label.setText(result)

        if result == UNDEFINED:
            label.hide()
            left_label.hide()
            self.adjustSize()

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Return):
            self.deleteLater()
    