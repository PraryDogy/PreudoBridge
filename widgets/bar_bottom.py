import os

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QWidget, QGridLayout

from cfg import Config


class BarBottom(QWidget):
    progressbar_start = pyqtSignal(int)
    progressbar_value = pyqtSignal(int)
    path_click = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setFixedHeight(20)
        self.path_label: QWidget = None

        self.h_lay = QGridLayout()
        self.h_lay.setContentsMargins(10, 0, 10, 0)
        self.setLayout(self.h_lay)

        self._progressbar = QProgressBar()
        self._progressbar.setFixedWidth(100)
        self.h_lay.addWidget(self._progressbar, 0, 1, alignment=Qt.AlignmentFlag.AlignRight)
        self._progressbar.hide()

        self.progressbar_start.connect(self._start_cmd)
        self.progressbar_value.connect(self._value_cmd)

        self.create_path_label()

    def _start_cmd(self, value: int):
        self._progressbar.setMaximum(value)
        self._progressbar.show()

    def _value_cmd(self, value: int):
        self._progressbar.setValue(value)

        if value == 1000000:
            self._progressbar.hide()

    def create_path_label(self):
        if isinstance(self.path_label, QWidget):
            self.path_label.close()

        self.path_label = QWidget()
        self.h_lay.addWidget(self.path_label, 0, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.setSpacing(0)
        self.path_label.setLayout(h_lay)

        root: str = Config.json_data.get("root")
        root = root.strip(os.sep).split(os.sep)
        for chunk in root:
            label = QLabel(" > " + chunk)
            label.mouseReleaseEvent = lambda e, c=chunk: self._new_root(root, c)
            h_lay.addWidget(label, alignment=Qt.AlignmentFlag.AlignLeft)

        h_lay.addStretch(1)

    def _new_root(self, rooted: list, chunk: str):
        new_path = rooted[:rooted.index(chunk) + 1]
        new_path = os.path.join(os.sep, *new_path)
        Config.json_data["root"] = new_path
        self.path_click.emit()