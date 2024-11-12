from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import QGraphicsDropShadowEffect, QWidget, QHBoxLayout


class SvgShadowed(QWidget):
    def __init__(self, icon_path: str, size: int, parent: QWidget = None):
        super().__init__(parent=parent)
        self.setStyleSheet(f"""background-color: transparent;""")
        effect = QGraphicsDropShadowEffect()
        effect.setOffset(0, 0)
        effect.setColor(QColor(0, 0, 0, 200))
        effect.setBlurRadius(15)
        self.setGraphicsEffect(effect)

        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(h_layout)

        self.svg_btn = QSvgWidget()
        self.svg_btn.renderer().setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self.svg_btn.setFixedSize(size, size)
        self.svg_btn.load(icon_path)
        h_layout.addWidget(self.svg_btn)
        self.adjustSize()
