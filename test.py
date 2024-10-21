from PyQt5.QtWidgets import QApplication, QLineEdit
from PyQt5.QtCore import QTranslator, QLocale, QLibraryInfo

app = QApplication([])

# Создаем объект для перевода
translator = QTranslator()

# Загружаем перевод на русский язык (по умолчанию путь идет к системным переводам Qt)
locale = QLocale.system().name()  # Определение локали системы, например 'ru_RU'
locale = "ru_RU"

if translator.load(f"qtbase_{locale}", QLibraryInfo.location(QLibraryInfo.TranslationsPath)):
    app.installTranslator(translator)

# Создаем QLineEdit и показываем его
line_edit = QLineEdit()
line_edit.show()

app.exec_()