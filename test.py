from PyQt5.QtWidgets import QPushButton, QWidget, QVBoxLayout, QLabel, QApplication
from PyQt5.QtCore import Qt
import sys

class ColorStarsBtn(QPushButton):
    def __init__(self):
        super().__init__(text="Фильтры")
        
        # Создаем кастомный виджет-меню
        self._menu_widget = QWidget()
        self._menu_widget.setWindowFlags(Qt.Popup)
        self._menu_widget.setLayout(QVBoxLayout())

        # Список цветов и их названия
        colors = {
            "🔴": "Red",
            "🔵": "Blue",
            "🟠": "Orange",
            "🟡": "Yellow",
            "🟢": "Green",
            "🟣": "Purple",
            "🟤": "Brown"
        }

        # Добавляем QLabel для каждого цвета
        self.labels = {}
        for emoji, name in colors.items():
            label = QLabel(f"{emoji} {name}")
            label.mousePressEvent = lambda event, color=name: self.toggle_label(color)
            self._menu_widget.layout().addWidget(label)

    def mouseReleaseEvent(self, e):
        self._menu_widget.move(self.mapToGlobal(self.rect().bottomLeft()))
        self._menu_widget.show()

    def toggle_label(self, color_name):
        print(color_name)

# Запуск приложения
app = QApplication(sys.argv)
window = ColorStarsBtn()
window.show()
sys.exit(app.exec_())