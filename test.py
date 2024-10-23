import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QHBoxLayout, QGridLayout
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from cfg import JsonData, Config

class SvgDisplayWidget(QWidget):
    def __init__(self):
        super().__init__()

        main_layout = QGridLayout()
        self.setLayout(main_layout)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(0)

        svg = "images/ded.jpg"
        colors = "🔴🟠🟡🟢"
        stars = "★★★★★"
        filename = "ded.jpg"

        col = 0
        first = QWidget()
        main_layout.addWidget(first, 0 , col)
        first_lay = QVBoxLayout()
        first.setLayout(first_lay)
        first.mouseReleaseEvent = lambda e, col=col: self.select_widget(first, col)

        svg_widget = QLabel()
        svg_widget.setPixmap(QPixmap(svg))
        first_lay.addWidget(svg_widget, alignment=Qt.AlignmentFlag.AlignTop)

        col += 1
        sec = QWidget()
        main_layout.addWidget(sec, 0 , col)
        sec_lay = QVBoxLayout()
        sec.setLayout(sec_lay)
        sec.mouseReleaseEvent = lambda e, col=col: self.select_widget(sec, col)

        svg_widget = QLabel()
        svg_widget.setPixmap(QPixmap(svg))
        sec_lay.addWidget(svg_widget, alignment=Qt.AlignmentFlag.AlignTop)

        lbl = QLabel(text=filename)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sec_lay.addWidget(lbl, alignment=Qt.AlignmentFlag.AlignBottom)

        col += 1
        third = QWidget()
        main_layout.addWidget(third, 0 , col)
        third_lay = QVBoxLayout()
        third.setLayout(third_lay)
        third.mouseReleaseEvent = lambda e, col=col: self.select_widget(third, col)

        svg_widget = QLabel()
        svg_widget.setPixmap(QPixmap(svg))
        third_lay.addWidget(svg_widget, alignment=Qt.AlignmentFlag.AlignTop)

        lbl = QLabel(text=f"{colors}\n{stars}\n{filename}")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        third_lay.addWidget(lbl, alignment=Qt.AlignmentFlag.AlignBottom)

        for i in (first, sec, third):
            i.adjustSize()
            print(i.height())

        self.deselect_widgets()

    def select_widget(self, wid: QWidget, index: int):
        self.deselect_widgets()
        wid.setStyleSheet("border: 1px solid white;")
        JsonData.view_rows = index
        Config.write_config()

    def deselect_widgets(self):
        for i in self.findChildren(QWidget):
            i.setStyleSheet("border: 1px solid transparent;")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SvgDisplayWidget()
    window.setWindowTitle("SVG and Unicode Example")
    window.resize(400, 600)  # Увеличен размер окна для лучшего отображения
    window.show()
    sys.exit(app.exec())
