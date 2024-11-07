import os
import subprocess
from datetime import datetime

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QContextMenuEvent, QMouseEvent, QPixmap
from PyQt5.QtWidgets import (QAction, QFrame, QGridLayout, QHBoxLayout, QLabel,
                             QMenu, QProgressBar, QSizePolicy, QWidget)

from cfg import BLUE, JsonData
from signals import SignalsApp
from utils import Utils

from ._base import BaseSlider
from ._thumb import Thumb
from .win_img_view import WinImgViewSingle
from .win_info import WinInfo

ARROW = " >"
IMAGES = "images"

DISK_SMALL = os.path.join(IMAGES, "disk_small.png")
FOLDER_SMALL = os.path.join(IMAGES, "folder_small.png")
MAC_SMALL = os.path.join(IMAGES, "mac_small.png")
FILE_SMALL = os.path.join(IMAGES, "file_small.png")


class CustomSlider(BaseSlider):

    def __init__(self):
        super().__init__(orientation=Qt.Orientation.Horizontal, minimum=0, maximum=3)
        self.setFixedWidth(80)
        self.setValue(JsonData.pixmap_size_ind)
        self.valueChanged.connect(self.change_size)
    
    def change_size(self, value: int):
        self.setValue(value)
        JsonData.pixmap_size_ind = value
        SignalsApp.all.resize_grid.emit()


class PathLabel(QLabel):
    _clicked = pyqtSignal(bool)

    def __init__(self, src: str, text: str):
        super().__init__(text)
        self.src = src
        self.setObjectName("path_label")

    def contextMenuEvent(self, ev: QContextMenuEvent | None) -> None:
        context_menu = QMenu(parent=self)

        view_action = QAction("Просмотр", self)
        cmd = lambda: self._clicked.emit(True)
        view_action.triggered.connect(cmd)
        context_menu.addAction(view_action)

        context_menu.addSeparator()

        info = QAction("Инфо", self)
        info.triggered.connect(self.show_info_win)
        context_menu.addAction(info)

        show_in_finder_action = QAction("Показать в Finder", self)
        show_in_finder_action.triggered.connect(self.show_in_finder)
        context_menu.addAction(show_in_finder_action)

        copy_path = QAction("Скопировать путь", self)
        copy_path.triggered.connect(lambda: Utils.copy_path(self.src))
        context_menu.addAction(copy_path)

        self.setStyleSheet(f"#path_label {{ background: {BLUE}; border-radius: 2px; }} ")
        context_menu.exec_(self.mapToGlobal(ev.pos()))
        self.setStyleSheet("")

    def show_info_win(self):
        # имя тип путь размер изменен
        self.win_info = WinInfo(self.get_info())
        Utils.center_win(parent=Utils.get_main_win(), child=self.win_info)
        self.win_info.show()

    def get_info(self):
        try:
            stats = os.stat(self.src)

            date = datetime.fromtimestamp(stats.st_mtime).replace(microsecond=0)
            date: str = date.strftime("%d.%m.%Y %H:%M")

            size_ = Utils.get_folder_size_applescript(self.src)
            if size_ < 1000:
                f_size = f"{size_} МБ"
            else:
                size_ = round(size_ / (1024**3), 2)
                f_size = f"{size_} ГБ"

            name = "Имя***" + os.path.basename(self.src)
            type = "Тип***" + "Папка"
            path = "Путь***" + self.src
            size = "Размер***" + f_size
            date = "Изменен***" + date
            return "\n".join([name, type, path, size, date])

        except (PermissionError, FileNotFoundError) as e:
            return "Ошибка данных: нет доступка к папке"

    def show_in_finder(self):
        subprocess.call(["open", "-R", self.src])


class PathItem(QWidget):
    def __init__(self, src: str, chunk_of_path: str, pixmap: QPixmap):
        super().__init__()
        self.src = src

        item_layout = QHBoxLayout()
        item_layout.setContentsMargins(0, 0, 0, 0)
        item_layout.setSpacing(5)
        self.setLayout(item_layout)

        self.icon_label = QLabel()
        self.icon_label.setPixmap(pixmap)
        item_layout.addWidget(self.icon_label)

        self.path_label = PathLabel(src=src, text=chunk_of_path + ARROW)
        self.path_label.setMinimumWidth(15)
        item_layout.addWidget(self.path_label)

        cmd = lambda e: self.new_root()
        self.mouseReleaseEvent = cmd

        cmd_ = lambda e, w=self.path_label: self.expand_temp(wid=w)
        self.enterEvent = cmd_
        cmd_ = lambda e, w=self.path_label: self.collapse_temp(wid=w)
        self.leaveEvent = cmd_

    def expand_temp(self, wid: QLabel | PathLabel):
        wid.setFixedWidth(wid.sizeHint().width())

    def collapse_temp(self, wid: QLabel | PathLabel):
        wid.setMinimumWidth(15)

    def new_root(self):
        SignalsApp.all.new_history.emit(self.src)
        SignalsApp.all.load_standart_grid.emit(self.src)
        SignalsApp.all.new_path_label.emit(None)

    def img_view(self, path: str, a0: QMouseEvent | bool):
        self.win_img_view = WinImgViewSingle(path)
        self.win_img_view.show()


class BarBottom(QWidget):
    def __init__(self):
        super().__init__()
        path_main_widget: QWidget = None

        self.grid_lay = QGridLayout()
        self.grid_lay.setContentsMargins(10, 5, 10, 0)
        self.grid_lay.setSpacing(5)
        self.setLayout(self.grid_lay)

        path_main_widget = QWidget()
        row, col, rowspan, colspan = 0, 0, 1, 3
        self.grid_lay.addWidget(path_main_widget, row, col, rowspan, colspan, Qt.AlignmentFlag.AlignLeft)

        sep = QFrame()
        sep.setStyleSheet("background: rgba(0, 0, 0, 0.2)")
        sep.setFixedHeight(1)
        row, col, rowspan, colspan = 1, 0, 1, 3
        self.grid_lay.addWidget(sep, row, col, rowspan, colspan)

        self.path_lay = QHBoxLayout()
        self.path_lay.setContentsMargins(0, 0, 0, 0)
        self.path_lay.setSpacing(5)
        path_main_widget.setLayout(self.path_lay)

        self.progressbar = QProgressBar()
        self.progressbar.setFixedHeight(15)
        self.progressbar.setFixedWidth(100)
        row, col = 2, 0
        self.grid_lay.addWidget(self.progressbar, row, col, alignment=Qt.AlignmentFlag.AlignRight)

        spacer = QWidget()
        spacer.setFixedWidth(10)
        row, col = 2, 1
        self.grid_lay.addWidget(spacer, row, col)

        self.slider = CustomSlider()
        self.progressbar.setFixedHeight(10)
        self.slider.setFixedWidth(70)
        row, col = 2, 2
        self.grid_lay.addWidget(self.slider, row, col, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.q_folder_small: QPixmap = self.small_icon(FOLDER_SMALL)
        self.q_disk_small: QPixmap = self.small_icon(DISK_SMALL)
        self.q_mac_small: QPixmap = self.small_icon(MAC_SMALL)

        SignalsApp.all.progressbar_value.connect(self.progressbar_value)
        SignalsApp.all.new_path_label.connect(self.create_path_labels)
        SignalsApp.all.new_path_label.emit(None)

    def small_icon(self, path: str):
        return QPixmap(path).scaled(15, 15, transformMode=Qt.TransformationMode.SmoothTransformation)

    def progressbar_value(self, value: int):
        if isinstance(value, int):
            self.progressbar.setValue(value)
        elif value == "hide":
            self.progressbar.hide()
        elif value == "show":
            self.progressbar.show()
        else:
            raise Exception("bar_borrom > progress bar wrong value", value)

    def create_path_labels(self, obj: Thumb | None):
        Utils.clear_layout(self.path_lay)

        root: str | list = JsonData.root
        root = root.strip(os.sep).split(os.sep)

        path_labels: list[tuple[QLabel, PathLabel]] = []

        for x, chunk_of_path in enumerate(root):
            src = os.path.join(os.sep, *root[:x + 1])
            
            path_item = PathItem(src, chunk_of_path, self.q_folder_small)

            self.path_lay.addWidget(path_item)
            path_labels.append((path_item.icon_label, path_item.path_label))

        # first = path_labels[0][0]
        # first.setPixmap(self.q_mac_small)

        # if len(path_labels) > 1:
        #     second = path_labels[1][0]
        #     second.setPixmap(self.q_disk_small)

        # if isinstance(obj, Thumb):
        #     icon_label = QLabel()
        #     icon_label.setPixmap(self.small_icon(obj.img))

        # last = temp[-1][1]
        # last.setText(last.text().replace(ARROW, ""))
        # if os.path.isfile(last.src):
        #     temp[-1][0].setPixmap(self.small_icon(FILE_SMALL))
