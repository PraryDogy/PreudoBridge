from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import (QLabel, QPushButton, QSizePolicy, QSpacerItem,
                             QWidget, QHBoxLayout, QVBoxLayout)

from system.shared_utils import SharedUtils

from ._base_widgets import MinMaxDisabledWin


class BaseWinWarn(MinMaxDisabledWin):
    svg_warning = "./icons/warning.svg"
    svg_size = 40

    def __init__(self, title: str, text: str, char_limit: int):
        super().__init__()
        self.setWindowTitle(title)
        self.setMinimumWidth(290)
        self.central_layout = QVBoxLayout()
        self.central_layout.setContentsMargins(0, 0, 0, 0)
        self.central_layout.setSpacing(0)
        # self.setMaximumWidth(370)

        h_wid = QWidget()
        self.central_layout.addWidget(h_wid)
        self.content_layout = QHBoxLayout()
        h_wid.setLayout(self.content_layout)

        warning = QSvgWidget()
        warning.load(self.svg_warning)
        warning.setFixedSize(self.svg_size, self.svg_size)
        self.content_layout.addWidget(warning)

        self.content_layout.addSpacerItem(QSpacerItem(15, 0))

        self.right_wid = QWidget()
        self.content_layout.addWidget(self.right_wid)
        self.right_layout = QVBoxLayout()
        self.right_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.right_wid.setLayout(self.right_layout)

        text = SharedUtils.insert_linebreaks(text, char_limit)
        self.text_label = QLabel(text)
        self.right_layout.addWidget(self.text_label)

        self.adjustSize()

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() in (Qt.Key.Key_Return, Qt.Key.Key_Escape):
            self.deleteLater()


class WinWarn(BaseWinWarn):
    text_ok = "Ок"

    def __init__(self, title: str, text: str, char_limit: int = 40):
        super().__init__(title, text, char_limit)
        ok_btn = QPushButton(text=self.text_ok)
        ok_btn.setFixedWidth(90)
        ok_btn.clicked.connect(self.deleteLater)
        self.central_layout.addWidget(ok_btn, alignment=Qt.AlignmentFlag.AlignCenter)


class WinQuestion(BaseWinWarn):
    ok_clicked = pyqtSignal()
    text_ok = "Ок"
    text_cancel = "Отмена"

    def __init__(self, title: str, text: str, char_limit = 40):
        super().__init__(title, text, char_limit)

        btn_wid = QWidget()
        btn_lay = QHBoxLayout()
        btn_lay.setSpacing(10)
        btn_wid.setLayout(btn_lay)

        ok_btn = QPushButton(self.text_ok)
        ok_btn.clicked.connect(self.ok_clicked.emit)
        ok_btn.setFixedWidth(90)

        cancel_btn = QPushButton(self.text_cancel)
        cancel_btn.setFixedWidth(90)
        cancel_btn.clicked.connect(self.deleteLater)

        btn_lay.addStretch()
        btn_lay.addWidget(ok_btn)
        btn_lay.addWidget(cancel_btn)
        btn_lay.addStretch()

        self.central_layout.addWidget(btn_wid)
