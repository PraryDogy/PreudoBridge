import os

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtWidgets import (QGridLayout, QHBoxLayout, QLabel, QProgressBar,
                             QWidget)

from cfg import PIXMAP_SIZE, JsonData
from signals import SIGNALS

from ._base import BaseSlider


class CustomSlider(BaseSlider):
    _clicked = pyqtSignal()

    def __init__(self):
        super().__init__(orientation=Qt.Orientation.Horizontal, minimum=0, maximum=3)
        self.setFixedWidth(80)
        self.setValue(PIXMAP_SIZE.index(JsonData.thumb_size))
        self.valueChanged.connect(self.change_size)
    
    def change_size(self, value: int):
        self.setValue(value)
        JsonData.thumb_size = PIXMAP_SIZE[value]
        self._clicked.emit()


class BarBottom(QWidget):
    folder_sym = "\U0001F4C1"
    progressbar_start = pyqtSignal(int)
    progressbar_value = pyqtSignal(int)
    resize_grid = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setFixedHeight(25)
        self.path_label: QWidget = None

        self.h_lay = QGridLayout()
        self.h_lay.setContentsMargins(10, 2, 10, 2)
        self.setLayout(self.h_lay)

        self._progressbar = QProgressBar()
        self._progressbar.setFixedWidth(100)
        self.h_lay.addWidget(self._progressbar, 0, 1, alignment=Qt.AlignmentFlag.AlignRight)
        self.progressbar_start.connect(self.start_cmd)
        self.progressbar_value.connect(self.value_cmd)

        self.slider = CustomSlider()
        self.slider.setFixedWidth(70)
        self.slider._clicked.connect(self.resize_grid.emit)
        self.h_lay.addWidget(self.slider, 0, 2, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.create_path_label()

    def start_cmd(self, value: int):
        self._progressbar.setMaximum(value)
        self._progressbar.show()

    def value_cmd(self, value: int):
        self._progressbar.setValue(value)

        if value == 1000000:
            self._progressbar.hide()

    def create_path_label(self):
        if isinstance(self.path_label, QWidget):
            self.path_label.close()

        self.path_label = QWidget()
        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.setSpacing(0)
        self.path_label.setLayout(h_lay)

        root: str = JsonData.root
        root = root.strip(os.sep).split(os.sep)

        chunks = []
        for chunk in root:
            label = QLabel(f"{BarBottom.folder_sym} {chunk} > ")
            label.mouseReleaseEvent = lambda e, c=chunk: self.new_root(e, root, c)
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

    def new_root(self, a0: QMouseEvent | None, rooted: list, chunk: str):
        if a0.button() == Qt.MouseButton.LeftButton:
            new_path = rooted[:rooted.index(chunk) + 1]
            new_path = os.path.join(os.sep, *new_path)
            JsonData.root = new_path
            SIGNALS.load_standart_grid.emit(None)