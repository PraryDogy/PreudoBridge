from PyQt5.QtWidgets import QWidget, QApplication, QGridLayout, QPushButton
from PyQt5.QtGui import QPainter, QColor, QBrush
from PyQt5.QtCore import QRect, Qt

class SelectionWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mass Selection Example")

        self.layout = QGridLayout(self)
        self.widgets: list[QPushButton] = []
        self.selection_rect = QRect()
        self.is_selecting = False

        # Создаем кнопки и добавляем их в сетку
        for i in range(4):
            for j in range(4):
                btn = QPushButton(f"Button {i},{j}", self)
                self.layout.addWidget(btn, i, j)
                self.widgets.append(btn)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_selecting = True
            self.selection_rect.setTopLeft(event.pos())
            self.selection_rect.setBottomRight(event.pos())
            self.update()

    def mouseMoveEvent(self, event):
        if self.is_selecting:
            self.selection_rect.setBottomRight(event.pos())
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_selecting = False

            for i in self.widgets:
                rect = i.geometry()

                if self.selection_rect.intersected(rect):
                    i.setStyleSheet("background: red;")

            self.selection_rect = QRect()
            self.update()

    def paintEvent(self, event):
        if self.is_selecting:
            painter = QPainter(self)
            painter.setBrush(QBrush(QColor(0, 120, 215, 100)))
            painter.setPen(Qt.NoPen)
            painter.drawRect(self.selection_rect)

if __name__ == "__main__":
    app = QApplication([])
    window = SelectionWidget()
    window.resize(400, 400)
    window.show()
    app.exec_()
