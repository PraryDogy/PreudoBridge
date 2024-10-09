from PyQt5.QtWidgets import QProgressBar, QWidget, QHBoxLayout
from PyQt5.QtCore import pyqtSignal, Qt, QTimer


class BarBottom(QWidget):
    progressbar_start = pyqtSignal(int)
    progressbar_value = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.setFixedHeight(30)

        h_lay = QHBoxLayout()
        self.setLayout(h_lay)

        self._progressbar = QProgressBar()
        self._progressbar.setFixedWidth(100)
        h_lay.addWidget(self._progressbar, alignment=Qt.AlignmentFlag.AlignRight)
        self._progressbar.hide()

        self.progressbar_start.connect(self._start_cmd)
        self.progressbar_value.connect(self._value_cmd)

    def _start_cmd(self, value: int):
        self._progressbar.setMaximum(value)
        self._progressbar.show()

    def _value_cmd(self, value: int):
        self._progressbar.setValue(value)

        if self._progressbar.value() == self._progressbar.maximum():
            self._progressbar.hide()