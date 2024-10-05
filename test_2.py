import sys
import os
from PyQt5.QtWidgets import QApplication, QListView, QFileSystemModel, QVBoxLayout, QWidget, QPushButton, QHBoxLayout
from PyQt5.QtCore import QModelIndex


class FileNavigator(QWidget):
    def __init__(self):
        super().__init__()

        # Создаем основной виджет для навигации
        self.layout = QVBoxLayout(self)

        # Кнопка "Назад"
        self.back_button = QPushButton("Назад")
        self.back_button.clicked.connect(self.go_back)
        self.back_button.setEnabled(False)  # Отключаем кнопку по умолчанию
        self.layout.addWidget(self.back_button)

        # Создаем модель файловой системы
        self.model = QFileSystemModel()
        self.model.setRootPath('')  # Устанавливаем корневой путь

        # Создаем QListView и привязываем модель
        self.list_view = QListView()
        self.list_view.setModel(self.model)
        self.list_view.setRootIndex(self.model.index(self.model.rootPath()))
        self.list_view.doubleClicked.connect(self.on_double_click)
        self.layout.addWidget(self.list_view)

        # Устанавливаем текущий путь
        self.current_path = self.model.rootPath()
        self.previous_paths = []  # Список для хранения предыдущих путей

    def on_double_click(self, index: QModelIndex):
        # Переход в директорию по двойному клику
        path = self.model.filePath(index)
        if self.model.isDir(index):
            self.previous_paths.append(self.current_path)
            self.set_root_path(path)

    def set_root_path(self, path: str):
        # Метод для обновления текущего каталога
        self.current_path = path
        self.list_view.setRootIndex(self.model.index(path))
        self.back_button.setEnabled(bool(self.previous_paths))

    def go_back(self):
        # Метод для возврата на предыдущую директорию
        if self.previous_paths:
            last_path = self.previous_paths.pop()
            self.set_root_path(last_path)


# Пример использования
if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Создаем и отображаем виджет FileNavigator
    window = FileNavigator()
    window.show()

    sys.exit(app.exec_())