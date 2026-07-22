import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QHBoxLayout, QLabel, QProgressBar, QVBoxLayout,
                             QWidget)

from cfg import Static

from ._base_widgets import UMainWidget, USvgSqareWidget


class CancelBtn(USvgSqareWidget):
    icon_size = 16
    svg_icon = os.path.join(Static.internal_images_dir, "clear.svg")
    clicked = pyqtSignal()

    def __init__(self):
        super().__init__(self.svg_icon, self.icon_size)

    def mouseReleaseEvent(self, a0):
        self.clicked.emit()
        return super().mouseReleaseEvent(a0)


class WinProgressbar(UMainWidget):
    progressbar_width = 300
    icon_path = os.path.join(Static.internal_images_dir, "copy_files.svg")
    icon_size = 50

    def __init__(self, title: str):
        super().__init__()
        self.set_always_on_top()
        self.set_close_only()
        self.setWindowTitle(title)

        self.central_layout.setContentsMargins(0, 5, 0, 5)
        self.central_layout.setSpacing(0)

        container = QWidget()
        self.central_layout.addWidget(container)

        main_lay = QHBoxLayout(container)
        main_lay.setContentsMargins(10, 5, 10, 5)
        main_lay.setSpacing(5)

        left_side_icon = USvgSqareWidget(self.icon_path, self.icon_size)
        main_lay.addWidget(left_side_icon)

        right_side_wid = QWidget()
        right_side_lay = QVBoxLayout(right_side_wid)
        right_side_lay.setContentsMargins(0, 0, 0, 0)
        right_side_lay.setSpacing(0)
        main_lay.addWidget(right_side_wid)

        self.above_label = QLabel()
        right_side_lay.addWidget(self.above_label)

        progressbar_row = QWidget()
        right_side_lay.addWidget(progressbar_row)
        progressbar_lay = QHBoxLayout(progressbar_row)
        progressbar_lay.setContentsMargins(0, 0, 0, 0)
        progressbar_lay.setSpacing(10)

        self.progressbar = QProgressBar()
        self.progressbar.setTextVisible(False)
        self.progressbar.setFixedHeight(6)
        self.progressbar.setFixedWidth(self.progressbar_width)
        progressbar_lay.addWidget(self.progressbar)

        self.cancel_btn = CancelBtn()
        progressbar_lay.addWidget(self.cancel_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.below_label = QLabel()
        right_side_lay.addWidget(self.below_label)

        self.above_label.setMaximumWidth(self.progressbar.width() - 10)
        self.below_label.setMaximumWidth(self.progressbar.width() - 10)

        self.adjustSize()

