from PyQt5.QtWidgets import QApplication, QWidget, QHBoxLayout, QLabel, QSizePolicy
from PyQt5.QtCore import Qt

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        layout = QHBoxLayout()

        # Создание 20 QLabel
        for i in range(20):
            label = QLabel(f"Label {i+1}")
            label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)  # Политика для растяжения
            layout.addWidget(label)

        # Устанавливаем Layout на окно
        self.setLayout(layout)

        # Устанавливаем окно с максимальной шириной для содержимого
        self.setWindowTitle('QLabel on Resize')
        self.setGeometry(100, 100, 600, 100)  # Начальный размер окна
        self.setMinimumWidth(100)  # Минимальная ширина окна
        self.show()

app = QApplication([])
window = MainWindow()
app.exec_()
