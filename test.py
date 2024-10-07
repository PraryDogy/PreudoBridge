from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QApplication, QHBoxLayout, QLabel, QVBoxLayout,
                             QWidget, QWidgetAction, QMenu, QSpacerItem)

import sys

class Filters(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() | Qt.Popup)
        v_layout = QVBoxLayout(self)
        v_layout.setContentsMargins(10, 10, 10, 10)
        v_layout.setSpacing(10)
        v_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setLayout(v_layout)

        color_wid = QWidget()
        v_layout.addWidget(color_wid)
        color_lay = QHBoxLayout()
        color_lay.setContentsMargins(0, 0, 0, 0)
        color_lay.setSpacing(5)
        color_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        color_wid.setLayout(color_lay)

        # черный и белый в пролете
        # замени цвета на unicode
        colors = "🔴🔵🟠🟡🟢🟣🟤"
        for color in colors:
            label = QLabel(text=color)
            label.mouseReleaseEvent = lambda e, c=color: print(c)
            color_lay.addWidget(label)

        stars_wid = QWidget()
        v_layout.addWidget(stars_wid)
        stars_lay = QHBoxLayout()
        stars_lay.setContentsMargins(0, 0, 0, 0)
        stars_lay.setSpacing(5)
        stars_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stars_wid.setLayout(stars_lay)

        for i in range(1, 6):
            label = QLabel(text="★")
            stars_lay.addWidget(label)
            

class FiltersBtn(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.menu = Filters(self)

    def mousePressEvent(self, event):
        self.menu.move(self.mapToGlobal(self.rect().bottomLeft()))
        self.menu.show()


class ColorContextMenuExample(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        # Настройка основного окна
        self.setWindowTitle("Color Context Menu Example")
        self.resize(300, 200)

        # Создаем QLabel для контекстного меню
        self.label = QLabel("Right-click to open color menu", self)
        self.label.setAlignment(Qt.AlignCenter)

        # Устанавливаем макет для окна
        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
        self.setLayout(layout)

        # Создаем контекстное меню
        self.menu = QMenu(self)

        for i in range(0, 5):
            self.menu.addAction(str(i))

        # Создаем подменю "Цвета"
        colors_menu = self.menu.addMenu("Цвета")

        # Список цветов с их названиями
        colors = {
            "🔴": "Red",
            "🔵": "Blue",
            "🟠": "Orange",
            "🟡": "Yellow",
            "🟢": "Green",
            "🟣": "Purple",
            "🟤": "Brown"
        }

        # Добавляем каждый цвет как действие в подменю
        for emoji, name in colors.items():
            action = colors_menu.addAction(f"{emoji} {name}")
            action.triggered.connect(lambda checked, c=name: self.select_color(c))

    def select_color(self, color_name):
        # Действие при выборе цвета
        print(f"Selected color: {color_name}")

    def contextMenuEvent(self, event):
        self.menu.exec_(event.globalPos())

# Запуск приложения
app = QApplication(sys.argv)
window = ColorContextMenuExample()
window.show()
sys.exit(app.exec_())