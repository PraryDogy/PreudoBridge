import os
import subprocess
from datetime import datetime

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QContextMenuEvent, QMouseEvent
from PyQt5.QtWidgets import (QAction, QGridLayout, QHBoxLayout, QLabel, QMenu,
                             QProgressBar, QWidget)

from cfg import BLUE, JsonData
from signals import SIGNALS
from utils import Utils

from ._base import BaseSlider
from .win_info import WinInfo


class CustomSlider(BaseSlider):

    def __init__(self):
        super().__init__(orientation=Qt.Orientation.Horizontal, minimum=0, maximum=3)
        self.setFixedWidth(80)
        self.setValue(JsonData.pixmap_size_ind)
        self.valueChanged.connect(self.change_size)
    
    def change_size(self, value: int):
        self.setValue(value)
        JsonData.pixmap_size_ind = value
        SIGNALS.resize_grid.emit()


class PathLabel(QLabel):
    _clicked = pyqtSignal()

    def __init__(self, src: str, text: str):
        super().__init__(text)
        self.src = src
        self.setObjectName("path_label")

    def contextMenuEvent(self, ev: QContextMenuEvent | None) -> None:
        context_menu = QMenu(parent=self)

        view_action = QAction("Просмотр", self)
        view_action.triggered.connect(self._clicked.emit)
        context_menu.addAction(view_action)

        context_menu.addSeparator()

        info = QAction("Инфо", self)
        info.triggered.connect(self.show_info_win)
        context_menu.addAction(info)

        show_in_finder_action = QAction("Показать в Finder", self)
        show_in_finder_action.triggered.connect(self.show_in_finder)
        context_menu.addAction(show_in_finder_action)

        copy_path = QAction("Скопировать путь до папки", self)
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

            size_ = round(stats.st_size / (1024**2), 2)
            if size_ < 1000:
                f_size = f"{stats.st_size} МБ"
            else:
                size_ = round(size_ / (1024**3), 2)
                f_size = f"{stats.st_size} ГБ"

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
    folder_sym = "\U0001F4C1"

    def __init__(self):
        super().__init__()
        SIGNALS.progressbar_value.connect(self.progressbar_value)
        self.setFixedHeight(25)
        self.path_label: QWidget = None

        self.h_lay = QGridLayout()
        self.h_lay.setContentsMargins(10, 2, 10, 2)
        self.setLayout(self.h_lay)

        self.progressbar = QProgressBar()
        self.progressbar.setFixedWidth(100)
        self.h_lay.addWidget(self.progressbar, 0, 1, alignment=Qt.AlignmentFlag.AlignRight)

        self.slider = CustomSlider()
        self.slider.setFixedWidth(70)
        self.h_lay.addWidget(self.slider, 0, 2, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.create_path_label()

    def progressbar_value(self, value: int):
        if self.progressbar.isHidden():
            self.progressbar.setValue(0)
            self.progressbar.setMaximum(value)
            self.progressbar.show()

        self.progressbar.setValue(value)

        if value == 1000000:
            self.progressbar.hide()

    def create_path_label(self):
        if isinstance(self.path_label, QWidget):
            self.path_label.close()

        self.path_label = QWidget()
        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.setSpacing(0)
        self.path_label.setLayout(h_lay)

        root: str = JsonData.root
        root: list = root.strip(os.sep).split(os.sep)

        chunks = []
        for x, chunk in enumerate(root):
            src = os.path.join(os.sep, *root[:x + 1])
            label = PathLabel(src=src, text=f"{BarBottom.folder_sym} {chunk} > ")
            label.mouseReleaseEvent = lambda e, c=chunk: self.new_root(root, c, e)
            label._clicked.connect(lambda c=chunk: self.new_root(root, c))
            h_lay.addWidget(label, alignment=Qt.AlignmentFlag.AlignLeft)
            chunks.append(label)

        t = chunks[-1].text().replace(" > ", "")
        chunks[-1].setText(t)

        h_lay.addStretch(1)

        self.path_label.adjustSize()
        ww = self.path_label.width()
        while ww > 430:
            chunks[0].hide()
            chunks.pop(0)
            self.path_label.adjustSize()
            ww = self.path_label.width()
        chunks.clear()
        self.h_lay.addWidget(self.path_label, 0, 0, alignment=Qt.AlignmentFlag.AlignLeft)

    def new_root(self, rooted: list, chunk: str, a0: QMouseEvent = None):
        if a0 is None or a0.button() == Qt.MouseButton.LeftButton:
            new_path = rooted[:rooted.index(chunk) + 1]
            new_path = os.path.join(os.sep, *new_path)
            SIGNALS.new_history.emit(new_path)
            SIGNALS.load_standart_grid.emit(new_path)
