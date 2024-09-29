import os
import sys
from PyQt5.QtWidgets import (
    QApplication, QTabWidget, QTreeWidget, QTreeWidgetItem, 
    QVBoxLayout, QWidget, QPushButton, QLineEdit, QLabel
)

class TreeWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)

        # Создаем QTreeWidget
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabel("Folders")

        # Заполняем QTreeWidget начальными данными
        self.load_directory(os.path.expanduser("~"))  # Загрузка домашней директории

        self.layout.addWidget(self.tree_widget)
        self.setLayout(self.layout)

    def load_directory(self, path):
        """Загрузить файлы и папки в QTreeWidget"""
        self.tree_widget.clear()  # Очистка перед загрузкой новых данных
        root_item = QTreeWidgetItem(self.tree_widget, [path])
        self.load_subdirectories(path, root_item)

    def load_subdirectories(self, path, parent_item):
        """Рекурсивная функция для загрузки подкаталогов"""
        try:
            for entry in os.listdir(path):
                full_path = os.path.join(path, entry)

                # Игнорируем скрытые файлы и ссылки
                if entry.startswith('.') or os.path.islink(full_path):
                    continue

                item = QTreeWidgetItem(parent_item, [entry])
                if os.path.isdir(full_path):
                    self.load_subdirectories(full_path, item)
        except PermissionError:
            pass  # Игнорируем папки, к которым нет доступа

class OpenDirectoryWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)

        # Создаем QTreeWidget
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabel("Open Directory")

        # Создаем QLineEdit для ввода пути
        self.path_input = QLineEdit(self)
        self.path_input.setPlaceholderText("Введите путь к директории")

        # Создаем кнопку для обновления дерева
        self.load_button = QPushButton("Загрузить", self)
        self.load_button.clicked.connect(self.load_directory)

        # Добавляем виджеты в layout
        self.layout.addWidget(QLabel("Путь:"))
        self.layout.addWidget(self.path_input)
        self.layout.addWidget(self.load_button)
        self.layout.addWidget(self.tree_widget)

        self.setLayout(self.layout)

    def load_directory(self):
        """Загрузить дерево для указанного пути"""
        path = self.path_input.text()
        if os.path.isdir(path):
            self.tree_widget.clear()  # Очистить текущее дерево
            root_item = QTreeWidgetItem(self.tree_widget, [path])
            self.load_subdirectories(path, root_item)
        else:
            self.tree_widget.clear()
            self.tree_widget.addTopLevelItem(QTreeWidgetItem([f"Ошибка: '{path}' не является директорией"]))

    def load_subdirectories(self, path, parent_item):
        """Рекурсивная функция для загрузки подкаталогов"""
        try:
            for entry in os.listdir(path):
                full_path = os.path.join(path, entry)

                # Игнорируем скрытые файлы и ссылки
                if entry.startswith('.') or os.path.islink(full_path):
                    continue

                item = QTreeWidgetItem(parent_item, [entry])
                if os.path.isdir(full_path):
                    self.load_subdirectories(full_path, item)
        except PermissionError:
            pass  # Игнорируем папки, к которым нет доступа

class MyApp(QTabWidget):
    def __init__(self):
        super().__init__()
        self.addTab(TreeWidget(), "Папки")
        self.addTab(OpenDirectoryWidget(), "Открывашка")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MyApp()
    window.setWindowTitle("Дерево папок с вкладками")
    window.resize(600, 400)
    window.show()
    sys.exit(app.exec_())

