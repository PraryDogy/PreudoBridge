import sys
from PyQt5.QtWidgets import QApplication, QWidget, QGridLayout, QLabel
from PyQt5.QtCore import Qt

class GridNavigation(QWidget):
    def __init__(self):
        super().__init__()
        self.rows = 3
        self.cols = 3
        self.initUI()

    def initUI(self):
        self.layout = QGridLayout()
        self.labels = []

        # Создаем сетку меток
        for r in range(self.rows):
            row_labels = []
            for c in range(self.cols):
                lbl = QLabel(f"Row {r}\nCol {c}")
                lbl.setAlignment(Qt.AlignCenter)
                lbl.setFixedSize(100, 100)
                
                # 1. Важно: разрешаем фокус
                lbl.setFocusPolicy(Qt.StrongFocus)
                
                # 2. Визуально выделяем фокус через стили
                lbl.setStyleSheet("""
                    QLabel { border: 2px solid #ccc; background: white; }
                    QLabel:focus { border: 2px solid #0078d7; background: #e1f5fe; }
                """)
                
                self.layout.addWidget(lbl, r, c)
                row_labels.append(lbl)
            self.labels.append(row_labels)

        self.setLayout(self.layout)
        self.setWindowTitle('Сетка навигации')
        
        # Устанавливаем начальный фокус на первую ячейку
        self.current_r = 0
        self.current_c = 0
        self.labels[0][0].setFocus()

    def keyPressEvent(self, event):
        # Логика перемещения индекса
        if event.key() == Qt.Key_Up:
            self.current_r = max(0, self.current_r - 1)
        elif event.key() == Qt.Key_Down:
            self.current_r = min(self.rows - 1, self.current_r + 1)
        elif event.key() == Qt.Key_Left:
            self.current_c = max(0, self.current_c - 1)
        elif event.key() == Qt.Key_Right:
            self.current_c = min(self.cols - 1, self.current_c + 1)
        else:
            super().keyPressEvent(event)
            return

        # Переводим фокус на нужный виджет
        self.labels[self.current_r][self.current_c].setFocus()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = GridNavigation()
    ex.show()
    sys.exit(app.exec_())

