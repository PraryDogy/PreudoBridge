import os

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QPushButton, QVBoxLayout

from ._base import ULineEdit, WinMinMax

FIND_HERE_PLACEHOLDER = "Введите имя или путь"


class WinFindHere(WinMinMax):
    finished_ = pyqtSignal(str)

    def __init__(self):
        super().__init__()          

        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(5, 5, 5, 5)
        self.setLayout(v_lay)

        self.text_edit = ULineEdit()
        self.text_edit.setPlaceholderText(FIND_HERE_PLACEHOLDER)
        self.text_edit.setFixedWidth(200)
        self.text_edit.clear_btn_vcenter()
        v_lay.addWidget(self.text_edit)

        self.text_edit.clear_btn_vcenter()

        ok_btn = QPushButton(text="Ок")
        ok_btn.setFixedWidth(90)
        ok_btn.clicked.connect(self.ok_btn_cmd)
        v_lay.addWidget(ok_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.adjustSize()
        self.setFixedSize(self.width(), self.height())

    def get_text(self):
        text = self.text_edit.text()
        text = text.strip()

        is_path = bool(
            os.path.isdir(text)
            or
            os.path.isfile(text)
        )

        if is_path:
            text = os.path.basename(text)

        return text
    
    def ok_btn_cmd(self, *args):

        self.finished_.emit(
            self.get_text()
        )

        self.close()

    def keyPressEvent(self, a0):
        if a0.key() == Qt.Key.Key_Escape:
            self.close()

        elif a0.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
            self.finished_.emit(
                self.get_text()
            )

            self.close()