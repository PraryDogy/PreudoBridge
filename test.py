from PyQt5.QtWidgets import QApplication, QLabel, QFrame, QVBoxLayout
from PyQt5.QtCore import Qt

app = QApplication([])
frame = QFrame()
layout = QVBoxLayout(frame)
label = QLabel("Очень длинный текст, который выходит за границы QFrame.")
label.setMinimumWidth(10)
label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
layout.addWidget(label)


# Двигаем текст влево при уменьшении окна
def adjust_label_position():
    label_width = label.sizeHint().width()
    frame_width = frame.width()
    x_offset = min(0, frame_width - label_width)  # Смещаем влево
    label.move(x_offset, label.y())

frame.resizeEvent = lambda event: adjust_label_position()


frame.show()
app.exec_()
