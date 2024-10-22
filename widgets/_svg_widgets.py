from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import QGraphicsDropShadowEffect, QWidget, QHBoxLayout


class SvgBtn(QWidget):
    def __init__(self, icon_path: str, size: int, parent: QWidget = None):

        self.icon_path = icon_path

        super().__init__(parent=parent)
        self.setStyleSheet(f"""background-color: transparent;""")

        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(h_layout)

        self.svg_btn = QSvgWidget()
        self.svg_btn.renderer().setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self.svg_btn.setFixedSize(size, size)
        self.set_icon(icon_path)
        h_layout.addWidget(self.svg_btn)
        self.adjustSize()

    def set_icon(self, icon_path):
        self.svg_btn.load(icon_path)

    def get_icon_path(self):
        return self.icon_path


class SvgShadowed(SvgBtn):
    def __init__(self, icon_name: str, size: int, shadow_depth: int = 200,
                 parent: QWidget = None):

        super().__init__(icon_name, size, parent)

        effect = QGraphicsDropShadowEffect()
        effect.setOffset(0, 0)
        effect.setColor(QColor(0, 0, 0, shadow_depth))
        effect.setBlurRadius(15)
        self.setGraphicsEffect(effect)