from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QApplication, QHBoxLayout, QLabel, QPushButton,
                             QWidget, QVBoxLayout)

app = QApplication([])

class Filters(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() | Qt.Popup)
        v_layout = QVBoxLayout(self)
        v_layout.setContentsMargins(5, 5, 5, 5)
        v_layout.setSpacing(0)
        self.setLayout(v_layout)

        color_wid = QWidget()
        v_layout.addWidget(color_wid)
        color_lay = QHBoxLayout()
        color_wid.setLayout(color_lay)

        # черный и белый в пролете
        # замени цвета на unicode
        colors = "🔴🔵🟠🟡🟢🟣🟤"
        for color in colors:
            label = QLabel(text=color)
            color_lay.addWidget(label)

        stars_wid = QWidget()
        v_layout.addWidget(stars_wid)
        stars_lay = QHBoxLayout()
        stars_wid.setLayout(stars_lay)

        for i in range(1, 6):
            label = QLabel(text="★" * i)
            stars_lay.addWidget(label)
            

class ClickableLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.menu = Filters(self)

    def mousePressEvent(self, event):
        self.menu.move(self.mapToGlobal(self.rect().bottomLeft()))
        self.menu.show()

app_label = ClickableLabel("Фильтры")
app_label.resize(100, 50)
app_label.show()

app.exec_()