import os

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QContextMenuEvent, QKeyEvent
from PyQt5.QtWidgets import QAction, QGridLayout, QLabel, QSpacerItem

from cfg import Static
from system.items import BaseItem
from system.shared_utils import SharedUtils
from system.tasks import ImgRes, MultipleItemsInfo, UThreadPool

from ._base_widgets import MinMaxDisabledWin, UMenu
from .actions import CopyText, RevealInFinder

# инфо 1 изображение
# инфо 1 файл
# инфо несколько файлов и папок (количество и размер)


class ULabel(QLabel):
    def __init__(self, text: str):
        super().__init__(text=text)
        self.setStyleSheet("font-size: 11px;")


class SelectableLabel(ULabel):
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

            reveal_action = RevealInFinder(menu, [src], 1)
            menu.addAction(reveal_action)

        menu.show_under_cursor()


class InfoWin(MinMaxDisabledWin):
    finished_ = pyqtSignal()
    title_text = "Инфо"
    calc_text = "Вычисляю..."

    ru_folder = "Папка: "
    name_text = "Имя:"
    type_text = "Тип:"
    size_text = "Размер:"
    src_text = "Место:"
    birth_text = "Создан:"
    mod_text = "Изменен:"
    resol_text = "Разрешение:"
    count_text = "Количество:"

    def __init__(self, items: list[BaseItem]):
        super().__init__()
        self.setWindowTitle(InfoWin.title_text)
        self.set_modality()

        self.items = items

        self.grid_layout = QGridLayout()
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)
        self.grid_layout.setSpacing(5)
        self.setLayout(self.grid_layout)

        self.init_ui()
        self.adjustSize()

    def init_ui(self):
        if len(self.items):
            if self.items[0].type_ in Static.ext_all:
                self.single_img()
            elif self.items[0].type_ == Static.FOLDER_TYPE:
                ...
            else:
                self.single_file()
        else:
            self.multiple_items()

    def single_img(self):
        row = 0
        item = self.items[0]
        labels = {
            self.name_text: item.filename,
            self.type_text: item.type_,
            self.size_text: SharedUtils.get_f_size(item.size),
            self.src_text: self.lined_text(item.src),
            self.birth_text: SharedUtils.get_f_date(item.birth),
            self.mod_text: SharedUtils.get_f_date(item.mod),
            self.resol_text: self.calc_text,
        }
        for k, v in labels.items():
            left = SelectableLabel(k)
            self.grid_layout.addWidget(left, row, 0, alignment=Qt.AlignmentFlag.AlignRight)
            self.grid_layout.addItem(QSpacerItem(10, 0), row, 1)
            right = SelectableLabel(v)
            self.grid_layout.addWidget(right, row, 2, alignment=Qt.AlignmentFlag.AlignLeft)
            row += 1

        resol_label = self.findChildren(SelectableLabel)[-1]
        if resol_label:
            self.img_res = ImgRes(item.src)
            self.img_res.sigs.finished_.connect(
                lambda text: resol_label.setText(text)
            )
            UThreadPool.start(self.img_res)

    def single_file(self):
        row = 0
        item = self.items[0]
        labels = {
            self.name_text: item.filename,
            self.type_text: item.type_,
            self.size_text: SharedUtils.get_f_size(item.size),
            self.src_text: self.lined_text(item.src),
            self.birth_text: SharedUtils.get_f_date(item.birth),
            self.mod_text: SharedUtils.get_f_date(item.mod),
        }
        for k, v in labels.items():
            left = SelectableLabel(k)
            self.grid_layout.addWidget(left, row, 0, alignment=Qt.AlignmentFlag.AlignRight)
            self.grid_layout.addItem(QSpacerItem(10, 0), row, 1)
            right = SelectableLabel(v)
            self.grid_layout.addWidget(right, row, 2, alignment=Qt.AlignmentFlag.AlignLeft)
            row += 1

    def multiple_items(self):
        row = 0
        labels = {
            self.size_text: self.calc_text,
            self.count_text: self.calc_text
        }
        for k, v in labels.items():
            left = SelectableLabel(k)
            self.grid_layout.addWidget(left, row, 0, alignment=Qt.AlignmentFlag.AlignRight)
            self.grid_layout.addItem(QSpacerItem(10, 0), row, 1)
            right = SelectableLabel(v)
            self.grid_layout.addWidget(right, row, 2, alignment=Qt.AlignmentFlag.AlignLeft)
            row += 1

        size_label = self.findChildren(SelectableLabel)[2]
        total_label = self.findChildren(SelectableLabel)[-1]
        self.info_task = MultipleItemsInfo(self.items)
        self.info_task.sigs.finished_.connect(
            lambda data: size_label.setText(data["total_size"])
        )
        self.info_task.sigs.finished_.connect(
            lambda data: total_label.setText(data["total_count"])
        )
        UThreadPool.start(self.info_task)

    def lined_text(self, text: str, limit: int = 50):
        if len(text) > limit:
            text = [
                text[i : i + limit]
                for i in range(0, len(text), limit)
                ]
            return "\n".join(text)
        else:
            return text

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Return):
            self.deleteLater()
    