from PyQt5.QtWidgets import QApplication, QWidget, QRadioButton, QVBoxLayout, QButtonGroup, QLabel, QPushButton, QHBoxLayout

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        layout = QHBoxLayout()

        # Создаем несколько радиокнопок
        radio_button1 = QPushButton("Option 1")
        radio_button2 = QPushButton("Option 2")
        radio_button3 = QPushButton("Option 3")

        # Добавляем их в макет
        layout.addWidget(radio_button1)
        layout.addWidget(radio_button2)
        layout.addWidget(radio_button3)

        # Создаем QButtonGroup и добавляем туда радиокнопки
        self.button_group = QButtonGroup(self)
        self.button_group.addButton(radio_button1, 1)  # 1 - это идентификатор кнопки
        self.button_group.addButton(radio_button2, 2)  # 2 - это идентификатор кнопки
        self.button_group.addButton(radio_button3, 3)  # 3 - это идентификатор кнопки

        # Создаем метку для вывода результата
        self.label = QLabel("Selected: None")
        layout.addWidget(self.label)

        # Подключаем обработчик нажатия кнопок
        self.button_group.buttonClicked[int].connect(self.on_button_clicked)

        self.setLayout(layout)

    def on_button_clicked(self, id):
        # Обработчик, который выводит идентификатор нажатой кнопки
        self.label.setText(f"Selected: Option {id}")

if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec_()