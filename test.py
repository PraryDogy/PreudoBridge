from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
import sys

class MultiDotWidget(QWidget):
    def __init__(self):
        super().__init__()
        
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Создаем QLabel с текстом и цветными точками
        label = QLabel()
        
        # Добавляем текст и цветные точки в HTML-код
        dots_html = '''
            <span style="color: yellow; font-weight: bold;">\u25CF</span>
            <span style="color: blue; font-weight: bold;">\u25CF</span>
            <span style="color: red; font-weight: bold;">\u25CF</span>
            <br>
            <span>Image 001.jpg</span>
        '''
        label.setText(dots_html)
        layout.addWidget(label)

app = QApplication(sys.argv)
window = MultiDotWidget()
window.show()
sys.exit(app.exec_())