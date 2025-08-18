import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QMessageBox

def show_error(msg: str):
    QMessageBox.critical(None, "Ошибка", msg)

def excepthook(exc_type, exc, tb):
    show_error(f"{exc_type.__name__}: {exc}")
    # опционально: sys.__excepthook__(exc_type, exc, tb)

app = QApplication(sys.argv)
sys.excepthook = excepthook

w = QWidget()
w.setWindowTitle("Ошибки")
btn = QPushButton("Показать ошибку")
btn.clicked.connect(lambda: show_error("Что-то пошло не так" * 50))
btn2 = QPushButton("Сгенерировать исключение")
btn2.clicked.connect(lambda: 1/0)

lay = QVBoxLayout(w)
lay.addWidget(btn)
lay.addWidget(btn2)
w.show()

sys.exit(app.exec_())
