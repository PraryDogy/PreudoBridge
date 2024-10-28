from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QLineEdit, QPushButton, QVBoxLayout, QWidget
from ._base import OnlyCloseWin

class WinRename(OnlyCloseWin):
    _finished = pyqtSignal(str)

    def __init__(self, text: str):
        super().__init__()
        self.setWindowTitle("Переименовать")
        self.setFixedSize(200, 70)

        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(10, 10, 10, 10)
        v_lay.setSpacing(10)
        self.setLayout(v_lay)

        self.input_wid = QLineEdit()
        self.input_wid.setText(text)
        self.input_wid.selectAll()
        v_lay.addWidget(self.input_wid)

        self.ok_btn = QPushButton(text="Ок")
        self.ok_btn.clicked.connect(self.finish_rename)
        self.ok_btn.setFixedWidth(100)
        v_lay.addWidget(self.ok_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.input_wid.setStyleSheet("padding-left: 2px; padding-right: 2px;")
        self.input_wid.setFixedSize(170, 25)

    def finish_rename(self):
        self._finished.emit(self.input_wid.text())
        self.close()

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() == Qt.Key.Key_Escape:
            self.close()
        elif a0.key() == Qt.Key.Key_Return:
            self.finish_rename()
        return super().keyPressEvent(a0)