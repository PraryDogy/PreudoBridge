from PyQt5.QtWidgets import QApplication, QListWidget, QMenu, QMessageBox
from PyQt5.QtCore import Qt

class TreeTags(QListWidget):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(150)
        self.setup_ui()

    def setup_ui(self):
        # Добавляем элементы
        self.addItem("—")  # Длинное тире
        for i in range(1, 6):
            self.addItem("★" * i)

        # Устанавливаем контекстное меню
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def show_context_menu(self, position):
        # Получаем текущий элемент
        item = self.itemAt(position)
        if not item:
            return

        # Создаем меню
        menu = QMenu()
        enable_action = menu.addAction("Включить")

        # Обработка выбранного действия
        menu.exec_(self.mapToGlobal(position))
