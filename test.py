import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QProgressBar
from PyQt5.QtCore import QTimer

class ProgressApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ProgressBar Example")
        self.setGeometry(100, 100, 300, 100)

        QApplication.setStyle("Fusion")

        self.layout = QVBoxLayout()
        self.progress = QProgressBar()
        self.progress.setMaximum(100)
        self.layout.addWidget(self.progress)
        self.setLayout(self.layout)

        self.timer = QTimer()
        self.timer.timeout.connect(self.advance)
        self.timer.start(1000)  # 1 секунда

        self.value = 0

        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)

    def advance(self):
        if self.value < 100:
            self.value += 10
            self.progress.setValue(self.value)
        else:
            self.timer.stop()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ProgressApp()
    window.show()
    sys.exit(app.exec_())
