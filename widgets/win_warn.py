from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWidgets import QPushButton, QVBoxLayout, QLabel

from ._base import WinMinMax

OK_T = "Ок"


class WinWarn(WinMinMax):

    def __init__(self, text: str):
        super().__init__()

        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(10, 10, 10, 10)
        v_lay.setSpacing(10)
        self.setLayout(v_lay)

        descr = QLabel(text=text)
        v_lay.addWidget(descr)

        self.ok_btn = QPushButton(text=OK_T)
        self.ok_btn.setFixedWidth(100)
        self.ok_btn.clicked.connect(self.close)
        v_lay.addWidget(self.ok_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.adjustSize()
        self.setFixedSize(self.width(), self.height())

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() == Qt.Key.Key_Escape:
            self.close()
        elif a0.key() == Qt.Key.Key_Return:
            self.close()
        return super().keyPressEvent(a0)