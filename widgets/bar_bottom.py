import os
import subprocess
from datetime import datetime

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QContextMenuEvent, QMouseEvent, QPixmap
from PyQt5.QtWidgets import (QAction, QFrame, QGridLayout, QHBoxLayout, QLabel,
                             QMenu, QProgressBar, QWidget)

from cfg import BLUE, JsonData
from signals import SignalsApp
from utils import Utils

from ._base import BaseSlider
from .win_img_view import WinImgViewSingle
from .win_info import WinInfo

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
    arrow = " > "

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
            return "Ошибка данных: нет доступка кт папке"

    def show_in_finder(self):
        subprocess.call(["open", "-R", self.src])


class BarBottom(QWidget):
    def __init__(self):
        super().__init__()
        SignalsApp.all.progressbar_value.connect(self.progressbar_value)
        # self.setFixedHeight(25)
        self.path_main_widget: QWidget = None

        self.grid_lay = QGridLayout()
        self.grid_lay.setContentsMargins(10, 2, 10, 2)
        self.setLayout(self.grid_lay)

        self.progressbar = QProgressBar()
        self.progressbar.setFixedWidth(100)
        self.grid_lay.addWidget(self.progressbar, 1, 1, alignment=Qt.AlignmentFlag.AlignRight)

        self.slider = CustomSlider()
        self.slider.setFixedWidth(70)
        self.grid_lay.addWidget(self.slider, 1, 2, alignment=Qt.AlignmentFlag.AlignVCenter)

        SignalsApp.all.new_path_label.connect(self.create_path_label)

        self.create_path_label()

    def progressbar_value(self, value: int):
        if self.progressbar.isHidden():
            self.progressbar.setValue(0)
            self.progressbar.setMaximum(value)
            self.progressbar.show()

        self.progressbar.setValue(value)

        if value == 1000000:
            self.progressbar.hide()

    def create_path_label(self, path: str = None):
        if isinstance(self.path_main_widget, QWidget):
            self.path_main_widget.close()

        self.path_main_widget = QWidget()
        self.grid_lay.addWidget(self.path_main_widget, 0, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.setSpacing(5)


        self.path_main_widget.setLayout(h_lay)

        if path:
            root: str | list = path
            root = root.strip(os.sep).split(os.sep)
        else:
            root: str | list = JsonData.root
            root = root.strip(os.sep).split(os.sep)

        path_labels: list[tuple[QLabel, PathLabel]] = []
        q_folder_small: QPixmap = self.small_icon(FOLDER_SMALL)

        for x, chunk_of_path in enumerate(root):

            src = os.path.join(os.sep, *root[:x + 1])
            is_dir = os.path.isdir(src)

            icon_label = QLabel()
            icon_label.setPixmap(q_folder_small)

            path_label = PathLabel(src=src, text=chunk_of_path + PathLabel.arrow)

            if is_dir:
                cmd = lambda e, c=chunk_of_path: self.new_root(rooted=root, chunk=c, a0=e)
                path_label.mouseReleaseEvent = cmd
                path_label._clicked.connect(cmd)

            else:
                cmd_ = lambda e, s=src: self.img_view(path=s, a0=e)
                path_label.mouseDoubleClickEvent = cmd_
                path_label._clicked.connect(cmd_)

            h_lay.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignLeft)
            h_lay.addWidget(path_label, alignment=Qt.AlignmentFlag.AlignLeft)

            path_labels.append((icon_label, path_label))

        h_lay.addStretch(1)

        first = path_labels[0][0]
        first.setPixmap(self.small_icon(MAC_SMALL))

        if len(path_labels) > 1:
            second = path_labels[1][0]
            second.setPixmap(self.small_icon(DISK_SMALL))

        last = path_labels[-1][1]
        last.setText(last.text().replace(PathLabel.arrow, ""))
        if os.path.isfile(last.src):
            path_labels[-1][0].setPixmap(self.small_icon(FILE_SMALL))

        self.path_main_widget.adjustSize()
        ww = self.width()

        while self.path_main_widget.width() > self.width():

            if len(path_labels) == 1:
                break

            path_labels[0][1].setText(PathLabel.arrow)
            path_labels.pop(0)
            self.path_main_widget.adjustSize()
            ww = self.width()

        path_labels.clear()

    def small_icon(self, path: str):
        return QPixmap(path).scaled(15, 15, transformMode=Qt.TransformationMode.SmoothTransformation)

    def new_root(self, rooted: list, chunk: str, a0: QMouseEvent | bool):
        if a0 is None or a0.button() == Qt.MouseButton.LeftButton:
            new_path = rooted[:rooted.index(chunk) + 1]
            new_path = os.path.join(os.sep, *new_path)
            SignalsApp.all.new_history.emit(new_path)
            SignalsApp.all.load_standart_grid.emit(new_path)

    def img_view(self, path: str, a0: QMouseEvent | bool):
        self.win_img_view = WinImgViewSingle(path)
        self.win_img_view.show()
