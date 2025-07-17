import os

from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtGui import QContextMenuEvent, QKeyEvent
from PyQt5.QtWidgets import QAction, QGridLayout, QLabel

from cfg import Static
from system.items import BaseItem
from system.utils import UImage, URunnable, UThreadPool, Utils

from ._base_widgets import MinMaxDisabledWin, UMenu
from .actions import CopyText, RevealInFinder


class _InfoTaskSigs(QObject):
    finished_info = pyqtSignal(dict)
    finished_calc = pyqtSignal(str)


class ImgResolTask(URunnable):
    undef_text = "Неизвестно"

    def __init__(self, base_item: BaseItem):
        super().__init__()
        self.base_item = base_item
        self.signals_ = _InfoTaskSigs()

    def task(self):
        img_ = UImage.read_image(self.base_item.src)
        if img_ is not None and len(img_.shape) > 1:
            h, w = img_.shape[0], img_.shape[1]
            resol= f"{w}x{h}"
        else:
            resol = self.undef_text
        
        self.signals_.finished_calc.emit(resol)


class FolderSizeTask(URunnable):
    undef_text = "Неизвестно"

    def __init__(self, base_item: BaseItem):
        super().__init__()
        self.base_item = base_item
        self.signals_ = _InfoTaskSigs()

    def task(self):
        try:
            total = self.get_folder_size()
        except Exception:
            Utils.print_error()
            total = self.undef_text

        self.signals_.finished_calc.emit(total)

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
        return Utils.get_f_size(total)



class InfoTask(URunnable):
    ru_folder = "Папка"
    calculating = "Вычисляю..."
    name_text = "Имя"
    type_text = "Тип"
    size_text = "Размер"
    src_text = "Место"
    mod_text = "Изменен"
    resol_text = "Разрешение"
    row_limit = 50

    def __init__(self, base_item: BaseItem):
        super().__init__()
        self.base_item = base_item
        self.signals = _InfoTaskSigs()

    def task(self) -> dict[str, str| int]:
        self.base_item.setup_attrs()

        if self.base_item.type_ == Static.FOLDER_TYPE:
            size_ = self.calculating
            type_ = self.ru_folder
        else:
            size_ = Utils.get_f_size(self.base_item.size)
            type_ = self.base_item.type_
        
        name = self.lined_text(self.base_item.name)
        src = self.lined_text(self.base_item.src)
        mod = Utils.get_f_date(self.base_item.mod)

        data = {
            InfoTask.name_text: name,
            InfoTask.type_text: type_,
            InfoTask.mod_text: mod,
            InfoTask.src_text: src,
            InfoTask.size_text: size_,
            }
        
        if self.base_item.type_ != Static.FOLDER_TYPE:
            data.update({InfoTask.resol_text: self.calculating})

        self.signals.finished_info.emit(data)

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
    finished_ = pyqtSignal()
    title_text = "Инфо"

    def __init__(self, src: str):
        super().__init__()
        self.setWindowTitle(InfoWin.title_text)
        self.set_modality()

        self.src = src
        self.base_item = BaseItem(self.src)

        self.grid_layout = QGridLayout()
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)
        self.grid_layout.setSpacing(5)
        self.setLayout(self.grid_layout)

        self.info_task = InfoTask(self.base_item)
        self.info_task.signals.finished_info.connect(lambda data: self.init_ui(data))
        UThreadPool.start(self.info_task)

    def init_ui(self, data: dict):
        row = 0

        for name, value in data.items():

            left_lbl = SelectableLabel(name)
            flags_l_al = Qt.AlignmentFlag.AlignRight
            self.grid_layout.addWidget(left_lbl, row, 0, alignment=flags_l_al)

            right_lbl = SelectableLabel(value)
            flags_r_al = Qt.AlignmentFlag.AlignLeft
            self.grid_layout.addWidget(right_lbl, row, 1, alignment=flags_r_al)

            row += 1

        self.adjustSize()
        self.finished_.emit()

        if self.base_item.type_ == Static.FOLDER_TYPE:
            self.calc_task = FolderSizeTask(self.base_item)
        else:
            self.calc_task = ImgResolTask(self.base_item)

        self.calc_task.signals_.finished_calc.connect(lambda res: self.finalize(res))
        UThreadPool.start(self.calc_task)


    def finalize(self, result: str):
        label = self.findChildren(SelectableLabel)[-1]
        label.setText(result)

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Return):
            self.deleteLater()
    