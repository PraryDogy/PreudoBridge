from PyQt5.QtWidgets import QApplication, QListView, QFileSystemModel, QAbstractItemView, QMessageBox
from PyQt5.QtCore import QModelIndex
import sys
import os

class FileNavigator(QListView):
    def __init__(self):
        super().__init__()

        # Создаем модель файловой системы
        self.model = QFileSystemModel()
        self.model.setRootPath('/Volumes')  # Устанавливаем корневой путь
        
        # Устанавливаем модель в QListView
        self.setModel(self.model)
        self.setRootIndex(self.model.index(self.model.rootPath()))

        # Устанавливаем корневой путь как текущий
        self.current_path = self.model.rootPath()

        # Подключаем событие двойного клика
        self.doubleClicked.connect(self.on_double_click)

    def add_up_directory_item(self):
        up_item = '..'
        self.model.insertRow(0)
        index = self.model.index(self.model.rootPath())
        self.model.setData(index, up_item)

    def on_double_click(self, index: QModelIndex):
        path = self.model.filePath(index)
        self.set_root_path(path)
    
    def set_root_path(self, path: str):
        self.current_path = path
        self.setRootIndex(self.model.index(path))

# Пример использования
if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Создаем и отображаем виджет FileNavigator
    navigator = FileNavigator()
    navigator.show()

    sys.exit(app.exec_())