from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QHBoxLayout, QLabel, QProgressBar, QVBoxLayout,
                             QWidget)

from cfg import Static

from ._base_widgets import MinMaxDisabledWin, USvgSqareWidget


class ProgressbarWin(MinMaxDisabledWin):

    progressbar_width = 300
    icon_size = 50

    def __init__(self, title: str, svg_icon: str):
        super().__init__()
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self.setWindowTitle(title)

        main_lay = QHBoxLayout()
        main_lay.setContentsMargins(10, 10, 10, 10)
        main_lay.setSpacing(5)
        self.setLayout(main_lay)

        left_side_icon = USvgSqareWidget(svg_icon, self.icon_size)
        main_lay.addWidget(left_side_icon)

        right_side_wid = QWidget()
        right_side_lay = QVBoxLayout()
        right_side_lay.setContentsMargins(0, 0, 0, 0)
        right_side_lay.setSpacing(0)
        right_side_wid.setLayout(right_side_lay)
        main_lay.addWidget(right_side_wid)

        self.above_label = QLabel()
        right_side_lay.addWidget(self.above_label)

        progressbar_row = QWidget()
        right_side_lay.addWidget(progressbar_row)
        progressbar_lay = QHBoxLayout()
        progressbar_lay.setContentsMargins(0, 0, 0, 0)
        progressbar_lay.setSpacing(10)
        progressbar_row.setLayout(progressbar_lay)

        self.progressbar = QProgressBar()
        self.progressbar.setTextVisible(False)
        self.progressbar.setFixedHeight(6)
        self.progressbar.setFixedWidth(self.progressbar_width)
        progressbar_lay.addWidget(self.progressbar)

        self.cancel_btn = USvgSqareWidget(Static.CLEAR_SVG, 16)
        self.cancel_btn.mouseReleaseEvent = self.cancel_cmd
        progressbar_lay.addWidget(self.cancel_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.below_label = QLabel()
        right_side_lay.addWidget(self.below_label)

        self.adjustSize()

    def cancel_cmd(self, *args):
        self.deleteLater()
