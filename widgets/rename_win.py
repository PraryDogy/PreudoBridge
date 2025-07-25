from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWidgets import QPushButton, QVBoxLayout, QLabel, QWidget, QHBoxLayout

from ._base_widgets import ULineEdit, MinMaxDisabledWin


class RenameWin(MinMaxDisabledWin):
    finished_ = pyqtSignal(str)
    placeholder_text = "Введите текст"
    ok_text = "Ок"
    cancel_text = "Отмена"
    title_text = "Задайте имя"
    descr_text = "Придумайте имя."
    input_width = 250

    def __init__(self, text: str):
        super().__init__()
        self.set_modality()
        self.setWindowTitle(RenameWin.title_text)

        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(10, 10, 10, 10)
        v_lay.setSpacing(10)
        self.setLayout(v_lay)

        descr = QLabel(RenameWin.descr_text)
        v_lay.addWidget(descr)

        self.input_wid = ULineEdit() 
        self.input_wid.setFixedWidth(RenameWin.input_width)
        self.input_wid.setPlaceholderText(RenameWin.placeholder_text)
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

        self.ok_btn = QPushButton(RenameWin.ok_text)
        self.ok_btn.clicked.connect(self.finish_rename)
        self.ok_btn.setFixedWidth(90)
        h_lay.addWidget(self.ok_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        cancel_btn = QPushButton(RenameWin.cancel_text)
        cancel_btn.clicked.connect(self.deleteLater)
        cancel_btn.setFixedWidth(90)
        h_lay.addWidget(cancel_btn)

        h_lay.addStretch()

        self.adjustSize()

    def finish_rename(self):
        self.finished_.emit(self.input_wid.text())
        self.deleteLater()

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() == Qt.Key.Key_Escape:
            self.deleteLater()
        elif a0.key() == Qt.Key.Key_Return:
            self.finish_rename()
        return super().keyPressEvent(a0)