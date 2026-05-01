import os

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QContextMenuEvent, QKeyEvent
from PyQt5.QtWidgets import (QAction, QGraphicsOpacityEffect, QGridLayout,
                             QLabel, QSpacerItem, QWidget)

from cfg import Static
from system.items import DataItem, MultipleInfoItem, NameUrlItem
from system.multiprocess import ImgRes, MultipleInfo, ProcessWorker
from system.shared_utils import ImgUtils, SharedUtils

from ._base_widgets import UMenu, WinMinCloseOnly, BaseSignals, WinWidget
from .actions import Actions


class ULabel(QLabel):
    def __init__(self, text: str):
        super().__init__(text=text)
        self.setStyleSheet("font-size: 11px;")


class SelectableLabel(ULabel):

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

    def contextMenuEvent(self, ev):
        ev.ignore()


class WinInfo(WinMinCloseOnly):
    finished_ = pyqtSignal()
    copy_text = pyqtSignal(str)

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


    def __init__(self, urls: list[str]):
        super().__init__()
        self.setWindowTitle(WinInfo.title_text)
        self.set_always_on_top()
        self.base_signals = BaseSignals()
        self.left = Qt.AlignmentFlag.AlignLeft
        self.right = Qt.AlignmentFlag.AlignRight
        self.top = Qt.AlignmentFlag.AlignTop
        self.data_items: list[DataItem] = []
        for i in urls:
            data_item = DataItem(i)
            data_item.set_properties()
            self.data_items.append(data_item)

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
            if not os.path.exists(self.data_items[0].abs_path):
                self
            if self.data_items[0].type_ in ImgUtils.ext_all:
                self.single_img()
            elif self.data_items[0].type_ == Static.folder_type:
                self.single_folder()
            else:
                self.single_file()
        else:
            self.multiple_items()

    def no_exitst_file():
        ...

    def single_img(self):

        def poll_task(resol_label: SelectableLabel):
            q = self.img_res_task.queue
            if not q.empty():
                resol = q.get()
                resol_label.setText(resol)
                self.set_transparent()
            if not self.img_res_task.is_alive():
                self.img_res_task.terminate_join()
            else:
                QTimer.singleShot(100, lambda: poll_task(resol_label))

        row = 0
        item = self.data_items[0]
        birth = int(os.stat(item.abs_path).st_birthtime)
        labels = {
            self.name_text: self.lined_text(item.filename),
            self.type_text: item.type_,
            self.size_text: SharedUtils.get_f_size(item.size),
            self.src_text: self.lined_text(item.abs_path),
            self.birth_text: SharedUtils.get_f_date(birth),
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
                args=(item.abs_path, )
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
            self.src_text: self.lined_text(item.abs_path),
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
            q = self.info_task.queue
            if not q.empty():
                info_item: MultipleInfoItem = q.get()
                total_size = self.findChildren(SelectableLabel)[3]
                total_files = self.findChildren(SelectableLabel)[5]
                total_folders = self.findChildren(SelectableLabel)[7]
                total_size.setText(info_item.total_size)
                total_files.setText(info_item.total_files)
                total_folders.setText(info_item.total_folders)
                self.set_transparent()
            
            if not self.info_task.is_alive():
                self.info_task.terminate_join()
            else:
                QTimer.singleShot(100, poll_task)

        row = 0
        root = os.path.dirname(self.data_items[0].abs_path)
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
            {"src": i.abs_path, "type_": i.type_, "size": i.size}
            for i in self.data_items
        ]

        self.info_task = ProcessWorker(
            target=MultipleInfo.start,
            args=(items, )
        )
        self.info_task.start()
        QTimer.singleShot(100, poll_task)

    def single_folder(self):

        def poll_task():
            q = self.info_task.queue
            if not q.empty():
                info_item: MultipleInfoItem = q.get()
                total_size = self.findChildren(SelectableLabel)[5]
                total_files = self.findChildren(SelectableLabel)[13]
                total_folders = self.findChildren(SelectableLabel)[15]
                total_size.setText(info_item.total_size)
                total_files.setText(info_item.total_files)
                total_folders.setText(info_item.total_folders)
                self.set_transparent()
            
            if not self.info_task.is_alive():
                self.info_task.terminate_join()
            else:
                QTimer.singleShot(100, poll_task)

        row = 0
        item = self.data_items[0]
        birth = int(os.stat(item.abs_path).st_birthtime)
        labels = {
            self.name_text: self.lined_text(item.filename),
            self.type_text: self.ru_folder,
            self.size_text: self.calc_text,
            self.src_text: self.lined_text(self.data_items[0].abs_path),
            self.birth_text: SharedUtils.get_f_date(birth),
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
            {"src": i.abs_path, "type_": i.type_, "size": i.size}
            for i in self.data_items
        ]

        self.info_task = ProcessWorker(
            target=MultipleInfo.start,
            args=(items, )
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
            self.img_res_task.terminate_join()
            self.info_task.terminate_join()
        except AttributeError:
            ...
        return super().deleteLater()

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() in (Qt.Key.Key_Escape, ):
            self.deleteLater()

    def contextMenuEvent(self, ev: QContextMenuEvent | None) -> None:
        widget: SelectableLabel = self.childAt(ev.pos())
        if not isinstance(widget, SelectableLabel):
            return

        text = widget.text().replace(Static.paragraph_symbol, "")
        text = text.replace(Static.line_feed_symbol, "")
        self.context_menu = UMenu()
        self.context_actions = Actions(self.context_menu)

        self.context_menu.add_action(
            action=self.context_actions.copy_text,
            callback=lambda: self.copy_text.emit(widget.selectedText())
        )
        self.context_menu.add_action(
            action=self.context_actions.select_all_text,
            callback=lambda: widget.setSelection(0, len(widget.text()))
        )
        if os.path.exists(text):
            self.context_menu.addSeparator()
            self.context_menu.add_action(
                action=self.context_actions.reveal,
                callback=lambda: self.base_signals.reveal_urls.emit([text, ])
            )
        self.context_menu.show_under_mouse()


class WinInfoFav(WinWidget):
    copy_text = pyqtSignal(str)
    name_text = "Имя в избранном"
    url_text = "Путь"

    def __init__(self, name_url_item: NameUrlItem):
        super().__init__()
        self.setWindowTitle(WinInfo.title_text)
        self.set_close_only()
        self.set_always_on_top()

        self.base_signals = BaseSignals()
        self.name_url_item = name_url_item
        self.left = Qt.AlignmentFlag.AlignLeft
        self.right = Qt.AlignmentFlag.AlignRight
        self.top = Qt.AlignmentFlag.AlignTop
        self.grid_layout = QGridLayout()
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.grid_layout.setContentsMargins(10, 15, 10, 15)
        self.grid_layout.setSpacing(5)
        self.setLayout(self.grid_layout)

        self.single_file()
        self.adjustSize()

    def center(self, *args):
        return

    def single_file(self):
        row = 0
        labels = {
            self.name_text: self.lined_text(self.name_url_item.name),
            self.url_text: self.lined_text(self.name_url_item.url)
        }
        for k, v in labels.items():
            left = SelectableLabel(k)
            self.grid_layout.addWidget(left, row, 0, alignment=self.right)
            self.grid_layout.addItem(QSpacerItem(10, 0), row, 1)
            right = SelectableLabel(v)
            self.grid_layout.addWidget(right, row, 2, alignment=self.left)
            row += 1

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
        if a0.key() in (Qt.Key.Key_Escape, ):
            self.deleteLater()

    def contextMenuEvent(self, ev: QContextMenuEvent | None) -> None:
        widget: SelectableLabel = self.childAt(ev.pos())
        if not isinstance(widget, SelectableLabel):
            return

        text = widget.text().replace(Static.paragraph_symbol, "")
        text = text.replace(Static.line_feed_symbol, "")
        self.context_menu = UMenu()
        self.context_actions = Actions(self.context_menu)

        self.context_menu.add_action(
            action=self.context_actions.copy_text,
            callback=lambda: self.copy_text.emit(widget.selectedText())
        )
        self.context_menu.add_action(
            action=self.context_actions.select_all_text,
            callback=lambda: widget.setSelection(0, len(widget.text()))
        )
        if os.path.exists(text):
            self.context_menu.addSeparator()
            self.context_menu.add_action(
                action=self.context_actions.reveal,
                callback=lambda: self.base_signals.reveal_urls.emit([text, ])
            )
        self.context_menu.show_under_mouse()