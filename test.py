from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QLineEdit, QVBoxLayout, QWidget
from PyQt5.QtCore import Qt

class RenameLabel(QLabel):
    def __init__(self, text):
        super().__init__(text)
        self.setText(text)
        
        # Линия редактирования для изменения текста
        self.line_edit = QLineEdit(self.text())
        self.line_edit.hide()
        
        # Когда редактирование завершено
        self.line_edit.editingFinished.connect(self.finish_edit)
        
    def mouseDoubleClickEvent(self, event):
        # Двойной щелчок активирует редактирование
        self.line_edit.setText(self.text())
        self.line_edit.show()
        self.line_edit.setFocus()
        self.hide()
        
    def finish_edit(self):
        # Завершаем редактирование и возвращаем текст в QLabel
        self.setText(self.line_edit.text())
        self.line_edit.hide()
        self.show()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Главный виджет и компоновка
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Создаем кастомный QLabel с возможностью переименования
        self.rename_label = RenameLabel("Дважды щелкните, чтобы переименовать")
        layout.addWidget(self.rename_label)
        layout.addWidget(self.rename_label.line_edit)
        
        self.setCentralWidget(widget)
        self.setWindowTitle("Переименование QLabel")

# app = QApplication([])
# window = MainWindow()
# window.show()
# app.exec_()

a = "🔴🟡🟢🟣"
a = [*a]
print(a)