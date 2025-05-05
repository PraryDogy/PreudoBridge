from PyQt5.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget
from PyQt5.QtCore import Qt, QRunnable, QThreadPool, pyqtSignal, QObject
from PyQt5.QtGui import QPixmap, QImage
from PIL import Image
from fit_img import FitImg
import sys
from utils import Utils

global_thread_pool = QThreadPool.globalInstance()

class ImageLoaderSignals(QObject):
    finished = pyqtSignal(QPixmap)

class ImageLoader(QRunnable):
    def __init__(self, path):
        super().__init__()
        self.path = path
        self.signals = ImageLoaderSignals()

    def run(self):
        for i in range(0, 3):
            print(i)
            image = Utils.read_image(self.path)
            image = FitImg.start(image, 300)
            pixmap = Utils.pixmap_from_array(image)

            try:
                self.signals.finished.emit(pixmap)
            except Exception:
                ...

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.label = QLabel("Загрузка...", alignment=Qt.AlignCenter)
        self.label.setFixedSize(300, 300)
        self.button = QPushButton("Загрузить фото")
        # self.button.clicked.connect(self.load_image)
        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.button)
        self.setLayout(layout)
        self.load_image()

    def load_image(self):
        task = ImageLoader("/Volumes/Macintosh HD/Users/Loshkarev/Desktop/TEST IMAGES/psd/2025-04-18 10-42-31 (B,R1,S1).psd")
        task.signals.finished.connect(self.label.setPixmap)
        global_thread_pool.start(task)

app = QApplication(sys.argv)
win = MainWindow()
win.show()
sys.exit(app.exec_())
