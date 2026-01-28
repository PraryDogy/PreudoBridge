import os

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QContextMenuEvent, QKeyEvent
from PyQt5.QtWidgets import (QAction, QGraphicsOpacityEffect, QGridLayout,
                             QLabel, QSpacerItem)

from cfg import JsonData, Static
from system.items import DataItem
from system.multiprocess import ImgRes, MultipleInfo, ProcessWorker
from system.shared_utils import SharedUtils

from ._base_widgets import MinMaxDisabledWin, UMenu
from .actions import CopyText, RevealInFinder


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

    def set_transparent_frame(self, value: float):
        effect = QGraphicsOpacityEffect(self)
        effect.setOpacity(value)
        self.setGraphicsEffect(effect)

    def contextMenuEvent(self, ev: QContextMenuEvent | None) -> None:

        src = self.text().replace(Static.paragraph_symbol, "")
        src = src.replace(Static.line_feed_symbol, "")

        menu = UMenu(parent=self)

        copy_action = CopyText(menu, self)
        menu.addAction(copy_action)

        select_all_act = QAction(SelectableLabel.select_all_text, menu)
        select_all_act.triggered.connect(self.select_all_cmd)
        menu.addAction(select_all_act)

        menu.addSeparator()

        reveal_action = RevealInFinder(menu, [src, ])
        menu.addAction(reveal_action)

        menu.show_under_cursor()


class InfoWin(MinMaxDisabledWin):
    finished_ = pyqtSignal()
    title_text = "Инфо"
    calc_text = "Вычисляю..."
    ru_folder = "Папка"
    name_text = "Имя:"
    type_text = "Тип:"
    size_text = "Размер:"
    src_text = "Место:"
    birth_text = "Создан:"
    mod_text = "Изменен:"
    resol_text = "Разрешение:"
    files_text = "Количество файлов:"
    folders_text = "Количество папок:"

    def __init__(self, data_items: list[DataItem]):
        super().__init__()
        self.setWindowTitle(InfoWin.title_text)
        self.set_modality()

        self.left = Qt.AlignmentFlag.AlignLeft
        self.right = Qt.AlignmentFlag.AlignRight
        self.top = Qt.AlignmentFlag.AlignTop
        self.data_items = data_items

        self.grid_layout = QGridLayout()
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)
        self.grid_layout.setSpacing(5)
        self.centralWidget().setLayout(self.grid_layout)

        self.init_ui()
        self.set_transparent()
        self.adjustSize()

    def set_transparent(self):
        for i in self.findChildren(SelectableLabel):
            if i.text() == self.calc_text:
                i.set_transparent_frame(0.5)
            else:
                i.set_transparent_frame(1)

    def init_ui(self):
        if len(self.data_items) == 1:
            if self.data_items[0].type_ in Static.img_exts:
                self.single_img()
            elif self.data_items[0].type_ == Static.folder_type:
                self.single_folder()
            else:
                self.single_file()
        else:
            self.multiple_items()

    def single_img(self):

        def poll_task(resol_label: SelectableLabel):
            q = self.img_res_task.get_queue()

            if not q.empty():
                resol = q.get()
                resol_label.setText(resol)
                self.set_transparent()

            if not self.img_res_task.proc.is_alive():
                self.img_res_task.terminate()
            else:
                QTimer.singleShot(100, lambda: poll_task(resol_label))

        row = 0
        item = self.data_items[0]
        labels = {
            self.name_text: self.lined_text(item.filename),
            self.type_text: item.type_,
            self.size_text: SharedUtils.get_f_size(item.size),
            self.src_text: self.lined_text(item.src),
            self.birth_text: SharedUtils.get_f_date(item.birth),
            self.mod_text: SharedUtils.get_f_date(item.mod),
            self.resol_text: self.calc_text,
        }
        for k, v in labels.items():
            left = SelectableLabel(k)
            self.grid_layout.addWidget(left, row, 0, alignment=self.right | self.top)
            self.grid_layout.addItem(QSpacerItem(10, 0), row, 1)
            right = SelectableLabel(v)
            self.grid_layout.addWidget(right, row, 2, alignment=self.left | self.top)
            row += 1

        resol_label = self.findChildren(SelectableLabel)[-1]

        if resol_label:
            self.img_res_task = ProcessWorker(
                target=ImgRes.start,
                args=(item.src, )
            )
            self.img_res_task.start()
            QTimer.singleShot(100, lambda: poll_task(resol_label))

    def single_file(self):
        row = 0
        item = self.data_items[0]
        labels = {
            self.name_text: self.lined_text(item.filename),
            self.type_text: item.type_,
            self.size_text: SharedUtils.get_f_size(item.size),
            self.src_text: self.lined_text(item.src),
            self.birth_text: SharedUtils.get_f_date(item.birth),
            self.mod_text: SharedUtils.get_f_date(item.mod),
        }
        for k, v in labels.items():
            left = SelectableLabel(k)
            self.grid_layout.addWidget(left, row, 0, alignment=self.right | self.top)
            self.grid_layout.addItem(QSpacerItem(10, 0), row, 1)
            right = SelectableLabel(v)
            self.grid_layout.addWidget(right, row, 2, alignment=self.left | self.top)
            row += 1

    def multiple_items(self):

        def poll_task():
            q = self.info_task.get_queue()
            if not q.empty():
                res = q.get()
                total_size = self.findChildren(SelectableLabel)[3]
                total_files = self.findChildren(SelectableLabel)[5]
                total_folders = self.findChildren(SelectableLabel)[7]
                total_size.setText(res["total_size"])
                total_files.setText(res["total_files"])
                total_folders.setText(res["total_folders"])
                self.set_transparent()
            
            if not self.info_task.proc.is_alive():
                self.info_task.terminate()
            else:
                QTimer.singleShot(100, poll_task)

        row = 0
        root = os.path.dirname(self.data_items[0].src)
        labels = {
            self.src_text: self.lined_text(root),
            self.size_text: self.calc_text,
            self.files_text: self.calc_text,
            self.folders_text: self.calc_text
        }
        for k, v in labels.items():
            left = SelectableLabel(k)
            self.grid_layout.addWidget(left, row, 0, alignment=self.right | self.top)
            self.grid_layout.addItem(QSpacerItem(10, 0), row, 1)
            right = SelectableLabel(v)
            self.grid_layout.addWidget(right, row, 2, alignment=self.left | self.top)
            row += 1

        items = [
            {"src": i.src, "type_": i.type_, "size": i.size}
            for i in self.data_items
        ]

        self.info_task = ProcessWorker(
            target=MultipleInfo.start,
            args=(items, JsonData.show_hidden, )
        )
        self.info_task.start()
        QTimer.singleShot(100, poll_task)

    def single_folder(self):

        def poll_task():
            q = self.info_task.get_queue()
            if not q.empty():
                res = q.get()
                total_size = self.findChildren(SelectableLabel)[5]
                total_files = self.findChildren(SelectableLabel)[13]
                total_folders = self.findChildren(SelectableLabel)[15]
                total_size.setText(res["total_size"])
                total_files.setText(res["total_files"])
                total_folders.setText(res["total_folders"])
                self.set_transparent()
            
            if not self.info_task.proc.is_alive():
                self.info_task.terminate()
            else:
                QTimer.singleShot(100, poll_task)

        row = 0
        item = self.data_items[0]
        labels = {
            self.name_text: self.lined_text(item.filename),
            self.type_text: self.ru_folder,
            self.size_text: self.calc_text,
            self.src_text: self.lined_text(self.data_items[0].src),
            self.birth_text: SharedUtils.get_f_date(item.birth),
            self.mod_text: SharedUtils.get_f_date(item.mod),
            self.files_text: self.calc_text,
            self.folders_text: self.calc_text
        }
        for k, v in labels.items():
            left = SelectableLabel(k)
            self.grid_layout.addWidget(left, row, 0, alignment=self.right | self.top)
            self.grid_layout.addItem(QSpacerItem(10, 0), row, 1)
            right = SelectableLabel(v)
            self.grid_layout.addWidget(right, row, 2, alignment=self.left | self.top)
            row += 1

        items = [
            {"src": i.src, "type_": i.type_, "size": i.size}
            for i in self.data_items
        ]

        self.info_task = ProcessWorker(
            target=MultipleInfo.start,
            args=(items, JsonData.show_hidden, )
        )
        self.info_task.start()
        QTimer.singleShot(100, poll_task)

    def lined_text(self, text: str, limit: int = 50):
        if len(text) > limit:
            text = [
                text[i : i + limit]
                for i in range(0, len(text), limit)
                ]
            return "\n".join(text)
        else:
            return text
        
    def deleteLater(self):
        try:
            self.img_res_task.terminate()
            self.info_task.terminate()
        except AttributeError:
            ...
        return super().deleteLater()

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Return):
            self.deleteLater()
    