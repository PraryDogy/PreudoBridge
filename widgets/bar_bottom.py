from PyQt5.QtWidgets import QProgressBar, QWidget, QHBoxLayout, QLabel
from PyQt5.QtCore import pyqtSignal, Qt, QTimer
from cfg import Config

class BarBottom(QWidget):
    progressbar_start = pyqtSignal(int)
    progressbar_value = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.setFixedHeight(20)

        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(10, 0, 10, 0)
        self.setLayout(h_lay)

        self.rooter = QLabel(text=Config.json_data.get("root"))
        h_lay.addWidget(self.rooter, alignment=Qt.AlignmentFlag.AlignLeft)

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

        if value == 1000000:
            self._progressbar.hide()
            print(111)