import sys
from PyQt5.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget
from PyQt5.QtCore import Qt

class ExampleApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QLabel с выравниванием текста")
        self.setGeometry(300, 300, 250, 150)

        layout = QVBoxLayout()
        self.setLayout(layout)

        label = QLabel("Текст одной строки")
        label.setFixedHeight(100)
        label.setAlignment(Qt.AlignTop)
        label.setStyleSheet("background: black;")
        layout.addWidget(label)
        

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ExampleApp()
    window.show()
    sys.exit(app.exec_())
