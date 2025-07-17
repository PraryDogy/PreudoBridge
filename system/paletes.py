from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtCore import Qt

class UPallete:

    @classmethod
    def light(cls):
        p = QPalette()
        p.setColor(QPalette.Window, QColor("#ffffff"))             # фон окон
        p.setColor(QPalette.WindowText, QColor("#000000"))         # обычный текст на окне
        p.setColor(QPalette.Base, QColor("#f5f5f5"))                # фон полей ввода
        p.setColor(QPalette.AlternateBase, QColor("#ffffff"))      # фон чередующихся строк (напр. в таблице)
        p.setColor(QPalette.ToolTipBase, QColor("#000000"))        # фон тултипа
        p.setColor(QPalette.ToolTipText, QColor("#ffffff"))        # текст тултипа
        p.setColor(QPalette.Text, QColor("#000000"))               # основной текст (в полях ввода, списках)
        p.setColor(QPalette.Button, QColor("#f0f0f0"))             # фон кнопок
        p.setColor(QPalette.ButtonText, QColor("#000000"))         # текст на кнопках
        p.setColor(QPalette.BrightText, QColor("#ff0000"))         # аварийный текст (например, ошибки)
        p.setColor(QPalette.Link, QColor("#007aff"))               # цвет ссылок
        p.setColor(QPalette.Highlight, QColor("#007aff"))          # фон выделения (напр. активная вкладка, выделение текста)
        p.setColor(QPalette.HighlightedText, QColor("#ffffff"))    # текст на фоне выделения
        return p

    @classmethod
    def dark(cls):
        p = QPalette()
        p.setColor(QPalette.Window, QColor("#1e1e1e"))
        p.setColor(QPalette.WindowText, QColor("#ffffff"))
        p.setColor(QPalette.Base, QColor("#191919"))
        p.setColor(QPalette.AlternateBase, QColor("#2a2a2a"))
        p.setColor(QPalette.ToolTipBase, QColor("#ffffff"))
        p.setColor(QPalette.ToolTipText, QColor("#000000"))
        p.setColor(QPalette.Text, QColor("#ffffff"))
        p.setColor(QPalette.Button, QColor("#2d2d2d"))
        p.setColor(QPalette.ButtonText, QColor("#ffffff"))
        p.setColor(QPalette.BrightText, QColor("#ff453a"))  # macOS red
        p.setColor(QPalette.Link, QColor("#0a84ff"))        # macOS system blue
        p.setColor(QPalette.Highlight, QColor("#0a84ff"))
        p.setColor(QPalette.HighlightedText, QColor("#000000"))
        return p
