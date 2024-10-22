import os

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (QGridLayout, QHBoxLayout, QLabel, QProgressBar,
                             QWidget, QSlider)
from PyQt5.QtGui import QMouseEvent

from cfg import JsonData, Config


class BarBottom(QWidget):
    folder_sym = "\U0001F4C1"
    # folder_sym = "\U0001F5C2"
    # folder_sym = ""
    progressbar_start = pyqtSignal(int)
    progressbar_value = pyqtSignal(int)
    path_click = pyqtSignal()

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
        # self._progressbar.hide()
        self.progressbar_start.connect(self.start_cmd)
        self.progressbar_value.connect(self.value_cmd)

        self.slider = QSlider(parent=self, orientation=Qt.Horizontal, minimum=0, maximum=3)
        self.slider.setFixedWidth(80)
        self.slider.setValue(Config.IMG_SIZES.index(JsonData.thumb_size))
        self.slider.valueChanged.connect(self.change_size)
        st = f"""
            QSlider::groove:horizontal {{
                border-radius: 1px;
                height: 3px;
                margin: 0px;
                background-color: rgba(111, 111, 111, 0.5);
            }}
            QSlider::handle:horizontal {{
                background-color: rgba(199, 199, 199, 1);
                height: 10px;
                width: 10px;
                border-radius: 5px;
                margin: -4px 0;
                padding: -4px 0px;
            }}
            """
        self.slider.setStyleSheet(st)

        self.h_lay.addWidget(self.slider, 0, 2, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.create_path_label()

    def change_size(self, value: int):
        self.slider.setValue(value)
        JsonData.thumb_size = Config.IMG_SIZES[value]
        self.path_click.emit()

    def start_cmd(self, value: int):
        self._progressbar.setMaximum(value)
        self._progressbar.show()

    def value_cmd(self, value: int):
        self._progressbar.setValue(value)

        if value == 1000000:
            return
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
        while ww > 485:
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
            self.path_click.emit()