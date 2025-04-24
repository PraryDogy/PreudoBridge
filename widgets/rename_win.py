from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWidgets import QPushButton, QVBoxLayout, QLabel, QWidget, QHBoxLayout

from ._base_items import ULineEdit, MinMaxDisabledWin

RENAME_PLACEHOLDER = "Введите текст"
OK_T = "Ок"
CANCEL_T = "Отмена"
TITLE_T = "Задайте имя"
DESCR_T = (
    "Придумайте имя для закладки.*",
    "*Необязательно."
)


class RenameWin(MinMaxDisabledWin):
    finished_ = pyqtSignal(str)

    def __init__(self, text: str):
        super().__init__()
        self.setFixedSize(300, 110)
        self.setWindowTitle(TITLE_T)

        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(5, 5, 5, 5)
        v_lay.setSpacing(5)
        self.setLayout(v_lay)

        descr = QLabel("\n".join(DESCR_T))
        v_lay.addWidget(descr)

        self.input_wid = ULineEdit() 
        self.input_wid.setFixedWidth(self.width() - 10)
        self.input_wid.setPlaceholderText(RENAME_PLACEHOLDER)
        self.input_wid.setText(text)
        self.input_wid.selectAll()
        v_lay.addWidget(self.input_wid)

        h_wid = QWidget()
        v_lay.addWidget(h_wid)
        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.setSpacing(10)
        h_wid.setLayout(h_lay)

        h_lay.addStretch()

        self.ok_btn = QPushButton(text=OK_T)
        self.ok_btn.clicked.connect(self.finish_rename)
        self.ok_btn.setFixedWidth(90)
        h_lay.addWidget(self.ok_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        cancel_btn = QPushButton(text=CANCEL_T)
        cancel_btn.clicked.connect(self.deleteLater)
        cancel_btn.setFixedWidth(90)
        h_lay.addWidget(cancel_btn)

        h_lay.addStretch()

    def finish_rename(self):
        self.finished_.emit(self.input_wid.text())
        self.deleteLater()

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() == Qt.Key.Key_Escape:
            self.deleteLater()
        elif a0.key() == Qt.Key.Key_Return:
            self.finish_rename()
        return super().keyPressEvent(a0)