import sys
from PyQt5.QtWidgets import QApplication, QTableView, QMainWindow
from PyQt5.QtCore import QDir, Qt
from PyQt5.QtWidgets import QFileSystemModel

class FileBrowserWindow(QMainWindow):
    def __init__(self, directory):
        super().__init__()

        # Модель файловой системы
        self.model = QFileSystemModel()
        self.model.setRootPath(directory)
        self.model.setFilter(QDir.NoDotAndDotDot | QDir.AllEntries)

        # Таблица для отображения файлов в виде списка
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setRootIndex(self.model.index(directory))  # Устанавливаем начальную директорию

        # Настройки таблицы
        self.table.setSelectionBehavior(QTableView.SelectRows)  # Выделение всей строки
        self.table.setSortingEnabled(True)  # Включаем сортировку по колонкам
        self.table.verticalHeader().setVisible(False)  # Отключаем нумерацию строк

        # Устанавливаем ширину колонок
        self.table.setColumnWidth(0, 250)  # Имя
        self.table.setColumnWidth(1, 100)  # Размер
        self.table.setColumnWidth(2, 100)  # Тип
        self.table.setColumnWidth(3, 150)  # Дата изменения

        # Сохраняем начальную сортировку
        self.current_sort_column = 0
        self.current_sort_order = Qt.AscendingOrder

        # Связываем сигналы
        self.table.horizontalHeader().sectionClicked.connect(self.save_sort_settings)
        self.model.directoryLoaded.connect(self.apply_sort_settings)

        # Настройки интерфейса
        self.setCentralWidget(self.table)
        self.setWindowTitle("File Browser")
        self.resize(800, 600)

    def save_sort_settings(self, index):
        """Сохраняем настройки сортировки при клике на заголовок колонки"""
        self.current_sort_column = index
        self.current_sort_order = self.table.horizontalHeader().sortIndicatorOrder()

    def apply_sort_settings(self):
        """Применяем сохраненную сортировку при обновлении содержимого папки"""
        self.table.sortByColumn(self.current_sort_column, self.current_sort_order)


app = QApplication(sys.argv)
window = FileBrowserWindow(QDir.homePath())  # Открываем домашнюю директорию
window.show()
sys.exit(app.exec_())