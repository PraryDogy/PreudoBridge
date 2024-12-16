from PyQt5.QtWidgets import QApplication, QMainWindow, QStatusBar, QLabel

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Статус-бар
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Лейблы для отображения информации
        self.item_count_label = QLabel("Элементов: 0")
        self.sort_type_label = QLabel("Сортировка: по имени")
        
        # Добавляем лейблы в статус-бар
        self.status_bar.addPermanentWidget(self.item_count_label)
        self.status_bar.addPermanentWidget(self.sort_type_label)
        
        # Установка основного окна
        self.setWindowTitle("Пример GUI")
        self.resize(400, 300)
        self.update_status(42, "по дате")

    def update_status(self, item_count, sort_type):
        self.item_count_label.setText(f"Элементов: {item_count}")
        self.sort_type_label.setText(f"Сортировка: {sort_type}")


app = QApplication([])
window = MainWindow()
window.show()
app.exec_()
