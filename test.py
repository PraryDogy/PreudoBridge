import sys
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication, QLabel, QMainWindow

class SpinnerWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Создаем метку для отображения спиннера
        self.spinner_label = QLabel(self)
        self.spinner_label.setAlignment(Qt.AlignCenter)
        self.spinner_label.setGeometry(100, 100, 100, 50)  # Позиция и размер

        # Список символов для спиннера с кругами
        self.spinner_symbols = ["◯", "◌", "⬤", "●"]
        self.current_symbol_index = 0

        # Настроим таймер для изменения текста
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_spinner)
        self.timer.start(200)  # Обновление каждую 200 миллисекунд

        self.setWindowTitle("Spinner with Circles")
        self.setGeometry(300, 300, 300, 200)

    def update_spinner(self):
        # Меняем текст на следующий символ спиннера
        self.spinner_label.setText(self.spinner_symbols[self.current_symbol_index])

        # Переходим к следующему символу в цикле
        self.current_symbol_index = (self.current_symbol_index + 1) % len(self.spinner_symbols)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SpinnerWindow()
    window.show()
    sys.exit(app.exec_())
