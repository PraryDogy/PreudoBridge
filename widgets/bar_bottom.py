import os
import subprocess
from datetime import datetime

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QContextMenuEvent, QPixmap
from PyQt5.QtWidgets import (QAction, QFrame, QGridLayout, QHBoxLayout, QLabel,
                             QMenu, QProgressBar, QWidget)

from cfg import BLUE, IMG_EXT, JsonData
from signals import SignalsApp
from utils import Utils

from ._base import BaseSlider
from ._thumb import Thumb
from .win_info import WinInfo

ARROW = " >"
IMAGES = "images"

DISK_SMALL = os.path.join(IMAGES, "disk_small.png")
FOLDER_SMALL = os.path.join(IMAGES, "folder_small.png")
MAC_SMALL = os.path.join(IMAGES, "mac_small.png")
FILE_SMALL = os.path.join(IMAGES, "file_small.png")



class Total(QThread):
    _finished = pyqtSignal(str, int)

    def __init__(self, src: str):
        super().__init__()
        self.src = src

    def run(self):
        count = sum(
            1
            for i in os.listdir(self.src)
            if not i.startswith(".") and (
                os.path.isdir(os.path.join(self.src, i)) or 
                i.endswith(IMG_EXT)
            )
        )
        self._finished.emit(self.src, count)

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
    _open_img_view = pyqtSignal()

    def __init__(self, obj: str | Thumb, text: str):
        super().__init__(text)
        self.obj = obj
        self.setObjectName("path_label")

    def contextMenuEvent(self, ev: QContextMenuEvent | None) -> None:
        context_menu = QMenu(parent=self)

        if isinstance(self.obj, Thumb):
            src = self.obj.src
        else:
            src = self.obj

        view_action = QAction("Просмотр", self)
        cmd = lambda: self._open_img_view.emit()
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
        copy_path.triggered.connect(self.copy_path)
        context_menu.addAction(copy_path)

        self.setStyleSheet(f"#path_label {{ background: {BLUE}; border-radius: 2px; }} ")
        context_menu.exec_(self.mapToGlobal(ev.pos()))
        self.setStyleSheet("")
    

    def copy_path(self):
        if isinstance(self.obj, Thumb):
            src = self.obj.src
        else:
            src = self.obj
        Utils.copy_path(src)

    def show_info_win(self):
        if isinstance(self.obj, Thumb):
            info = self.obj.get_info()
        else:
            info = self.get_info(self.obj)

        self.win_info = WinInfo(info)
        Utils.center_win(parent=Utils.get_main_win(), child=self.win_info)
        self.win_info.show()

    def get_info(self, src: str):
        try:
            stats = os.stat(src)

            date = datetime.fromtimestamp(stats.st_mtime).replace(microsecond=0)
            date: str = date.strftime("%d.%m.%Y %H:%M")

            size_ = Utils.get_folder_size_applescript(src)
            if size_ < 1000:
                f_size = f"{size_} МБ"
            else:
                size_ = round(size_ / (1024**3), 2)
                f_size = f"{size_} ГБ"

            name = "Имя***" + os.path.basename(src)
            type = "Тип***" + "Папка"
            path = "Путь***" + src
            size = "Размер***" + f_size
            date = "Изменен***" + date
            return "\n".join([name, type, path, size, date])

        except (PermissionError, FileNotFoundError) as e:
            return "Ошибка данных: нет доступка к папке"

    def show_in_finder(self):
        if isinstance(self.obj, Thumb):
            src = self.obj.src
        else:
            src = self.obj
        subprocess.call(["open", "-R", src])


class PathItem(QWidget):
    def __init__(self, obj: str | Thumb, name: str, pixmap: QPixmap):
        super().__init__()
        self.setFixedHeight(15)
        self.obj = obj

        item_layout = QHBoxLayout()
        item_layout.setContentsMargins(0, 0, 0, 0)
        item_layout.setSpacing(5)
        self.setLayout(item_layout)

        self.icon_label = QLabel()
        self.icon_label.setPixmap(pixmap)
        item_layout.addWidget(self.icon_label)
        
        self.path_label = PathLabel(obj=obj, text=name + ARROW)
        self.path_label.setMinimumWidth(15)
        item_layout.addWidget(self.path_label)

        self.mouseReleaseEvent = self.new_root
        self.path_label._open_img_view.connect(self.new_root)

        cmd_ = lambda e, w=self.path_label: self.expand_temp(wid=w)
        self.enterEvent = cmd_
        cmd_ = lambda e, w=self.path_label: self.collapse_temp(wid=w)
        self.leaveEvent = cmd_

    def expand_temp(self, wid: QLabel | PathLabel):
        wid.setFixedWidth(wid.sizeHint().width())

    def collapse_temp(self, wid: QLabel | PathLabel):
        wid.setMinimumWidth(15)
 
    def new_root(self, *args):
        if isinstance(self.obj, Thumb):
            self.obj.open_in_view.emit()
        else:
            SignalsApp.all.new_history.emit(self.obj)
            SignalsApp.all.load_standart_grid.emit(self.obj)


class BarBottom(QWidget):
    def __init__(self):
        super().__init__()
        path_main_widget: QWidget = None

        self.grid_lay = QGridLayout()
        self.grid_lay.setContentsMargins(10, 5, 10, 0)
        self.grid_lay.setSpacing(5)
        self.setLayout(self.grid_lay)

        path_main_widget = QWidget()
        row, col, rowspan, colspan = 0, 0, 1, 4
        self.grid_lay.addWidget(path_main_widget, row, col, rowspan, colspan, Qt.AlignmentFlag.AlignLeft)

        sep = QFrame()
        sep.setStyleSheet("background: rgba(0, 0, 0, 0.2)")
        sep.setFixedHeight(1)
        row, col, rowspan, colspan = 1, 0, 1, 4
        self.grid_lay.addWidget(sep, row, col, rowspan, colspan)

        self.path_lay = QHBoxLayout()
        self.path_lay.setContentsMargins(0, 0, 0, 0)
        self.path_lay.setSpacing(5)
        path_main_widget.setLayout(self.path_lay)

        self.total = QLabel()
        self.total.setFixedHeight(15)
        row, col = 2, 0
        self.grid_lay.addWidget(self.total, row, col, Qt.AlignmentFlag.AlignLeft)

        self.progressbar = QProgressBar()
        self.progressbar.setFixedSize(100, 10)
        row, col = 2, 1
        self.grid_lay.addWidget(self.progressbar, row, col)

        h_spacer = QWidget()
        h_spacer.setFixedSize(10, 15)
        row, col = 2, 2
        self.grid_lay.addWidget(h_spacer, row, col)

        self.slider = CustomSlider()
        self.slider.setFixedSize(70, 15)
        row, col = 2, 3
        self.grid_lay.addWidget(self.slider, row, col)

        self.q_folder_small: QPixmap = self.small_icon(FOLDER_SMALL)
        self.q_disk_small: QPixmap = self.small_icon(DISK_SMALL)
        self.q_mac_small: QPixmap = self.small_icon(MAC_SMALL)

        SignalsApp.all.progressbar_value.connect(self.progressbar_value)
        SignalsApp.all.new_path_label.connect(self.create_path_labels)

    def small_icon(self, obj: str | QPixmap):
        if isinstance(obj, str):
            return QPixmap(obj).scaled(15, 15, transformMode=Qt.TransformationMode.SmoothTransformation)
        else:
            return obj.scaled(15, 15, transformMode=Qt.TransformationMode.SmoothTransformation)

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

        self.total.setText("Загрузка")
        root: str | list = JsonData.root
        root = root.strip(os.sep).split(os.sep)
        path_items: list[PathItem] = []

        for x, name in enumerate(root, start=1):
            src = os.path.join(os.sep, *root[:x + 1])
            path_item = PathItem(src, name, self.q_folder_small)
            path_items.append(path_item)
            self.path_lay.addWidget(path_item)

        path_items[0].icon_label.setPixmap(self.q_mac_small)

        if len(path_items) > 1:
            path_items[1].icon_label.setPixmap(self.q_disk_small)

        if isinstance(obj, Thumb):
            pixmap = self.small_icon(obj.img)
            path_item = PathItem(obj, obj.name, pixmap)
            self.path_lay.addWidget(path_item)
            path_items.append(path_item)
        else:
            # все файлы а не только фотки
            self.task = Total(JsonData.root)
            self.task._finished.connect(self.finished_total)
            self.task.start()

        last = path_items[-1].path_label
        last.setText(last.text().replace(ARROW, ""))

    def finished_total(self, src: str, count: int):
        if src == JsonData.root:
            self.total.setText("Всего: " + str(count))
