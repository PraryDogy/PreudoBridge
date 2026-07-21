import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout

from cfg import Static

from ._base_widgets import BtnSmall, UMainWindow


class ConfirmWindow(UMainWindow):
    ok_clicked = pyqtSignal()
    ww = 360
    svg_icon = os.path.join(Static.internal_images_dir, "warning.svg")

    def __init__(self, text: str):
        super().__init__()
        self.set_always_on_top()
        self.set_close_only()
        self.setWindowTitle("Внимание!")
        self.setFixedWidth(350)

        self.central_layout = QVBoxLayout(self.centralWidget())
        self.central_layout.setContentsMargins(10, 10, 10, 5)
        self.central_layout.setSpacing(5)

        text_layout = QHBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(15)
        self.central_layout.addLayout(text_layout)

        svg_wid = QSvgWidget()
        svg_wid.load(self.svg_icon)
        svg_wid.setFixedSize(50, 50)
        text_layout.addWidget(svg_wid)

        text_wid = QLabel(text)
        text_wid.setWordWrap(True)
        text_wid.adjustSize()
        text_layout.addWidget(text_wid)

        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(10)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.central_layout.addLayout(btn_layout)

        self.ok_btn = BtnSmall("Ок")
        self.ok_btn.setFixedWidth(90)
        self.ok_btn.clicked.connect(self.ok_clicked.emit)
        btn_layout.addWidget(self.ok_btn)

        self.cancel_btn = BtnSmall("Отмена")
        self.cancel_btn.setFixedWidth(90)
        self.cancel_btn.clicked.connect(self.deleteLater)
        btn_layout.addWidget(self.cancel_btn)

        self.adjustSize()

    def keyPressEvent(self, a0):
        if a0.key() == Qt.Key.Key_Escape:
            self.deleteLater()
        elif a0.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.ok_clicked.emit()
        return super().keyPressEvent(a0)
    

class WinWarn(ConfirmWindow):
    def __init__(self, text):
        super().__init__(text)
        self.cancel_btn.hide()
        self.cancel_btn.deleteLater()
        self.ok_btn.disconnect()
        self.ok_btn.clicked.connect(self.deleteLater)

    def keyPressEvent(self, a0):
        if a0.key() == Qt.Key.Key_Escape:
            self.deleteLater()
        elif a0.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.deleteLater()
        return super().keyPressEvent(a0)