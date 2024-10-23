import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QHBoxLayout, QGridLayout
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from cfg import JsonData, Config

class ViewThumbWidget(QWidget):
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
        simple_view = QWidget()
        simple_view.setObjectName("sett_thumb")
        simple_view.setStyleSheet("#sett_thumb { border: 1px solid transparent; }")
        simple_view.mouseReleaseEvent = lambda e, col=col: self.select_widget(simple_view, col)
        main_layout.addWidget(simple_view, 0 , col)

        simple_view_lay = QVBoxLayout()
        simple_view.setLayout(simple_view_lay)

        image_label = QLabel()
        image_label.setPixmap(QPixmap(svg))
        simple_view_lay.addWidget(image_label, alignment=Qt.AlignmentFlag.AlignTop)



        col += 1
        info_view = QWidget()
        info_view.setObjectName("sett_thumb")
        info_view.setStyleSheet("#sett_thumb { border: 1px solid transparent; }")
        info_view.mouseReleaseEvent = lambda e, col=col: self.select_widget(info_view, col)
        main_layout.addWidget(info_view, 0 , col)

        info_view_lay = QVBoxLayout()
        info_view.setLayout(info_view_lay)

        image_label = QLabel()
        image_label.setPixmap(QPixmap(svg))
        info_view_lay.addWidget(image_label, alignment=Qt.AlignmentFlag.AlignTop)

        text_label = QLabel(text=f"{colors}\n{stars}\n{filename}")
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_view_lay.addWidget(text_label, alignment=Qt.AlignmentFlag.AlignBottom)
        info_view.setObjectName("sett_thumb")

        if JsonData.name_label_h == 0:
            self.set_white(simple_view)
        else:
            self.set_white(info_view)

    def set_transparent(self, wid: QWidget):
        wid.setStyleSheet("#sett_thumb { border: 1px solid transparent; }")

    def set_white(self, wid: QWidget):
        wid.setStyleSheet("#sett_thumb { border: 1px solid white; }")

    def select_widget(self, wid: QWidget, index: int):
        self.deselect_widgets()
        self.set_white(wid)
        JsonData.name_label_h = index
        Config.write_config()

    def deselect_widgets(self):
        for i in self.findChildren(QWidget):
            self.set_transparent(i)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ViewThumbWidget()
    window.setWindowTitle("SVG and Unicode Example")
    window.resize(400, 600)  # Увеличен размер окна для лучшего отображения
    window.show()
    sys.exit(app.exec())
