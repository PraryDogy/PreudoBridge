import sys
from PyQt5.QtWidgets import QApplication, QWidget, QTabWidget, QVBoxLayout, QLineEdit

class SimpleTabApp(QWidget):
    def __init__(self):
        super().__init__()

        # Настройка главного окна
        self.setWindowTitle('PyQt5 Tabs & LineEdit')
        self.setGeometry(300, 300, 400, 200)

        # Создаем основной макет
        layout = QVBoxLayout()

        # Создаем виджет вкладок
        self.tabs = QTabWidget()
        self.tabs.tabBar().hide()

        # Создаем первую вкладку
        self.tab1 = QWidget()
        self.tab1_layout = QVBoxLayout()
        self.line_edit1 = QLineEdit()
        self.line_edit1.setPlaceholderText("Введите текст на вкладке 1...")
        self.tab1_layout.addWidget(self.line_edit1)
        self.tab1.setLayout(self.tab1_layout)

        # Создаем вторую вкладку
        self.tab2 = QWidget()
        self.tab2_layout = QVBoxLayout()
        self.line_edit2 = QLineEdit()
        self.line_edit2.setPlaceholderText("Введите текст на вкладке 2...")
        self.tab2_layout.addWidget(self.line_edit2)
        self.tab2.setLayout(self.tab2_layout)

        # Добавляем вкладки в QTabWidget
        self.tabs.addTab(self.tab1, "Вкладка 1")
        self.tabs.addTab(self.tab2, "Вкладка 2")

        # Добавляем виджет вкладок в главный макет
        layout.addWidget(self.tabs)
        self.setLayout(layout)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = SimpleTabApp()
    ex.show()
    sys.exit(app.exec_())
