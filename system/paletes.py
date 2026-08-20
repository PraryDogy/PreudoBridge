from PyQt6.QtGui import QColor, QPalette


class UPallete:

    @classmethod
    def light(cls):
        p = QPalette()
        color = QPalette.ColorRole
        p.setColor(color.Window, QColor("#ffffff"))
        p.setColor(color.WindowText, QColor("#000000"))
        p.setColor(color.Base, QColor("#f5f5f5"))
        p.setColor(color.AlternateBase, QColor("#ffffff"))
        p.setColor(color.ToolTipBase, QColor("#ffffff"))   
        p.setColor(color.ToolTipText, QColor("#000000"))   
        p.setColor(color.Text, QColor("#000000"))
        p.setColor(color.Button, QColor("#f0f0f0"))
        p.setColor(color.ButtonText, QColor("#000000"))
        p.setColor(color.BrightText, QColor("#ff0000"))
        p.setColor(color.Link, QColor("#0059d1"))
        p.setColor(color.Highlight, QColor("#0059d1"))
        p.setColor(color.HighlightedText, QColor("#ffffff"))
        return p

    @classmethod
    def dark(cls):
        p = QPalette()
        color = QPalette.ColorRole
        p.setColor(color.Window, QColor("#1e1e1e"))
        p.setColor(color.WindowText, QColor("#ffffff"))
        p.setColor(color.Base, QColor("#191919"))
        p.setColor(color.AlternateBase, QColor("#2a2a2a"))
        p.setColor(color.ToolTipBase, QColor("#2a2a2a"))   
        p.setColor(color.ToolTipText, QColor("#ffffff"))   
        p.setColor(color.Text, QColor("#ffffff"))
        p.setColor(color.Button, QColor("#2d2d2d"))
        p.setColor(color.ButtonText, QColor("#ffffff"))
        p.setColor(color.BrightText, QColor("#ff453a"))
        p.setColor(color.Link, QColor("#0059d1"))
        p.setColor(color.Highlight, QColor("#0059d1"))
        p.setColor(color.HighlightedText, QColor("#000000"))
        return p

    @classmethod
    def macinthosh(cls):
        p = QPalette()
        color = p.ColorRole
        p.setColor(color.Highlight, QColor("#0059d1"))
        return p
