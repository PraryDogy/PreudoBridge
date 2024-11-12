from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWidgets import QPushButton, QVBoxLayout, QWidget

from ._base import ULineEdit, WinMinMax

RENAME_T = "Переименовать"
OK_T = "Ок"


class WinRename(WinMinMax):
    _finished = pyqtSignal(str)

    def __init__(self, text: str):
        super().__init__()
        self.setWindowTitle(RENAME_T)
        self.setFixedSize(200, 70)

        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(10, 10, 10, 10)
        v_lay.setSpacing(10)
        self.setLayout(v_lay)

        self.input_wid = ULineEdit()
        self.input_wid.setText(text)
        self.input_wid.selectAll()
        v_lay.addWidget(self.input_wid)

        self.ok_btn = QPushButton(text=OK_T)
        self.ok_btn.clicked.connect(self.finish_rename)
        self.ok_btn.setFixedWidth(100)
        v_lay.addWidget(self.ok_btn, alignment=Qt.AlignmentFlag.AlignCenter)

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