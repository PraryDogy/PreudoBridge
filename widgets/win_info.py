from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWidgets import QGridLayout, QLabel, QWidget
from PyQt5.QtCore import Qt

class WinInfo(QWidget):
    def __init__(self, text: str) -> None:
        super().__init__()
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlags(Qt.Window | Qt.CustomizeWindowHint | Qt.WindowCloseButtonHint)
        self.setWindowTitle("Инфо")

        self.grid_layout = QGridLayout()
        self.grid_layout.setContentsMargins(10, 10, 10, 10)
        self.grid_layout.setSpacing(5)
        self.setLayout(self.grid_layout)

        row = 0

        for line in text.split("\n"):
            left_text, right_text = line.split(":")
            left_text, right_text = left_text.strip(), right_text.strip()

            if len(right_text) > 50:
                max_row = 35
                right_text = [
                    right_text[i:i + max_row]
                    for i in range(0, len(right_text), max_row)
                    ]
                right_text = "\n".join(right_text)

            left_lbl = QLabel(left_text)
            al = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
            self.grid_layout.addWidget(left_lbl, row, 0, alignment=al)

            right_lbl = QLabel(right_text)
            al = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom
            self.grid_layout.addWidget(right_lbl, row, 1, alignment=al)

            row += 1

        w = 350
        self.adjustSize()
        self.setMinimumWidth(w)
        self.setFixedHeight(self.height())
        self.resize(self.height(), w)
   
    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() == Qt.Key.Key_Escape:
            self.close()