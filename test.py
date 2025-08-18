from PyQt5.QtWidgets import QApplication, QDialog, QVBoxLayout, QTextEdit, QPushButton
import sys

app = QApplication(sys.argv)
d = QDialog()
l = QVBoxLayout(d)
l.addWidget(QTextEdit("Очень длинная ошибка\n"*50, readOnly=True))
l.addWidget(QPushButton("Закрыть", clicked=d.close))
d.resize(500, 400)
d.exec_()
