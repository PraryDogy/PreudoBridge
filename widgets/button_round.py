from PyQt5.QtCore import QSize
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtWidgets import QApplication, QLabel, QMainWindow, QPushButton


class ButtonRound(QLabel):
    def __init__(self, text):
        super().__init__(text)
        self.ww = 20
        self.setFixedSize(self.ww, self.ww)
        self.setStyleSheet(f"border-radius: {self.ww//2}px;")

        self.checked: bool = False

    def set_checked(self, b: bool):
        self.checked = b

        if self.checked:
            self.setStyleSheet(f"background: red; border-radius: {self.ww//2}px;")
        else:
            self.setStyleSheet(f"background: transparent; border-radius: {self.ww//2}px;")

    def mouseReleaseEvent(self, ev: QMouseEvent | None) -> None:
        b = not self.checked
        self.set_checked(b)
        return super().mouseReleaseEvent(ev)