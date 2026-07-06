from PyQt6.QtGui import QColor, QPalette


class UPallete:

    @classmethod
    def light(cls):
        p = QPalette()
        # Для удобства создаем короткую ссылку на перечисление
        role = QPalette.ColorRole
        
        p.setColor(role.Window, QColor("#ffffff"))             # фон окон
        p.setColor(role.WindowText, QColor("#000000"))         # обычный текст на окне
        p.setColor(role.Base, QColor("#f5f5f5"))               # фон полей ввода
        p.setColor(role.AlternateBase, QColor("#ffffff"))      # фон чередующихся строк
        p.setColor(role.ToolTipBase, QColor("#000000"))        # фон тултипа
        p.setColor(role.ToolTipText, QColor("#ffffff"))        # текст тултипа
        p.setColor(role.Text, QColor("#000000"))               # основной текст
        p.setColor(role.Button, QColor("#f0f0f0"))             # фон кнопок
        p.setColor(role.ButtonText, QColor("#000000"))         # текст на кнопках
        p.setColor(role.BrightText, QColor("#ff0000"))         # аварийный текст
        p.setColor(role.Link, QColor("#007aff"))               # цвет ссылок
        p.setColor(role.Highlight, QColor("#007aff"))          # фон выделения
        p.setColor(role.HighlightedText, QColor("#ffffff"))    # текст на фоне выделения
        return p

    @classmethod
    def dark(cls):
        p = QPalette()
        role = QPalette.ColorRole
        
        p.setColor(role.Window, QColor("#1e1e1e"))
        p.setColor(role.WindowText, QColor("#ffffff"))
        p.setColor(role.Base, QColor("#191919"))
        p.setColor(role.AlternateBase, QColor("#2a2a2a"))
        p.setColor(role.ToolTipBase, QColor("#ffffff"))
        p.setColor(role.ToolTipText, QColor("#000000"))
        p.setColor(role.Text, QColor("#ffffff"))
        p.setColor(role.Button, QColor("#2d2d2d"))
        p.setColor(role.ButtonText, QColor("#ffffff"))
        p.setColor(role.BrightText, QColor("#ff453a"))          # macOS red
        p.setColor(role.Link, QColor("#0a84ff"))               # macOS system blue
        p.setColor(role.Highlight, QColor("#0a84ff"))
        p.setColor(role.HighlightedText, QColor("#000000"))
        return p
