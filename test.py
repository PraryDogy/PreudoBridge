from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QApplication, QHBoxLayout, QLabel, QPushButton,
                             QWidget)

app = QApplication([])

class HorizontalMenu(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() | Qt.Popup)  # Окно закрывается при клике вне
        layout = QHBoxLayout(self)
        
        # Добавляем кнопки как пункты меню
        button1 = QPushButton("Option 1")
        button1.clicked.connect(lambda: self.menu_action("Option 1"))
        
        button2 = QPushButton("Option 2")
        button2.clicked.connect(lambda: self.menu_action("Option 2"))
        
        layout.addWidget(button1)
        layout.addWidget(button2)

    def menu_action(self, option):
        print(f"{option} selected")
        # self.close()  # Закрываем меню после выбора опции

class ClickableLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.menu = HorizontalMenu(self)

    def mousePressEvent(self, event):
        # Показываем меню под меткой
        self.menu.move(self.mapToGlobal(self.rect().bottomLeft()))
        self.menu.show()

app_label = ClickableLabel("Click me")
app_label.resize(100, 50)
app_label.show()

app.exec_()