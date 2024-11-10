from PyQt5.QtGui import QContextMenuEvent, QKeyEvent
from PyQt5.QtWidgets import QGridLayout, QLabel, QWidget
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QLabel, QMenu, QWidget
from PyQt5.QtCore import Qt
from ._base import WinMinMax


STRANGE_SYM = " "


class CustomLabel(QLabel):
    def __init__(self, text: str):
        super().__init__(text)

    def contextMenuEvent(self, ev: QContextMenuEvent | None) -> None:
        self.setSelection(0, len(self.text()))
        menu = QMenu(self)
        copy_action = menu.addAction("Копировать")
        copy_action.triggered.connect(self.custom_copy)
        menu.exec_(ev.globalPos())

    def custom_copy(self):
        selected_text = self.selectedText()
        modified_text = selected_text.replace(STRANGE_SYM, "")
        clipboard = QApplication.clipboard()
        clipboard.setText(modified_text)


class WinInfo(WinMinMax):
    def __init__(self, text: str, split_sym: str = "***") -> None:
        super().__init__()
        self.setWindowTitle("Инфо")

        self.grid_layout = QGridLayout()
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)
        self.grid_layout.setSpacing(5)
        self.setLayout(self.grid_layout)

        row = 0

        for line in text.split("\n"):
            left_text, right_text = line.split(split_sym)
            left_text, right_text = left_text.strip(), right_text.strip()
            max_row = 38

            if len(right_text) > max_row:
                right_text = [
                    right_text[i:i + max_row]
                    for i in range(0, len(right_text), max_row)
                    ]
                right_text = "\n".join(right_text)

            left_lbl = CustomLabel(left_text)
            flags_l_al = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
            self.grid_layout.addWidget(left_lbl, row, 0, alignment=flags_l_al)

            right_lbl = CustomLabel(right_text)
            flags_r = Qt.TextInteractionFlag.TextSelectableByMouse
            right_lbl.setTextInteractionFlags(flags_r)
            flags_r_al = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom
            self.grid_layout.addWidget(right_lbl, row, 1, alignment=flags_r_al)

            row += 1

        w = 350
        self.adjustSize()
        self.setMinimumWidth(w)
        self.setFixedHeight(self.height())
        self.resize(self.height(), w)
   
    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() == Qt.Key.Key_Escape:
            self.close()
