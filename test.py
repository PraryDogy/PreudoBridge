import sys
import os
from PyQt5.QtGui import QPainter, QColor, QFont
from PyQt5.QtSvg import QSvgRenderer, QSvgGenerator
from PyQt5.QtCore import QSize, QRect, QRectF, Qt
from PyQt5.QtWidgets import QApplication


class IconGenerator:
    @classmethod
    def create_icon(cls, text: str, base_icon_path: str, icon_path: str):
        renderer = QSvgRenderer(base_icon_path)
        width, height = 133, 133
        text_to_draw = text[:4].upper()

        generator = QSvgGenerator()
        generator.setFileName(icon_path)
        generator.setSize(QSize(width, height))
        generator.setViewBox(QRect(0, 0, width, height))

        painter = QPainter(generator)
        renderer.render(painter)
        painter.setPen(QColor(71, 84, 103))
        painter.setFont(QFont("Arial", 29, QFont.Bold))
        painter.drawText(QRectF(0, 75, width, 30), Qt.AlignCenter, text_to_draw)
        painter.end()

        return icon_path


if __name__ == "__main__":
    app = QApplication(sys.argv)

    TEXT_EXTENSIONS = [
        ".txt", ".md", ".csv", ".log", ".ini", ".cfg", ".conf", ".json", ".yaml", ".yml", ".xml", ".html", ".htm",
        ".css", ".js", ".ts", ".jsx", ".tsx", ".php", ".rb", ".pl", ".sh", ".bat", ".ps1", ".java", ".c", ".cpp",
        ".h", ".hpp", ".cs", ".go", ".rs", ".swift", ".kt", ".m", ".mm", ".py", ".r", ".sql", ".lua", ".asm", ".s",
        ".dart", ".scala", ".groovy", ".vb", ".bas", ".f90", ".f", ".f95"
    ]

    base_icon = "_text_icon.svg"
    output_dir = "new"
    os.makedirs(output_dir, exist_ok=True)

    for ext in TEXT_EXTENSIONS:
        out_path = os.path.join(output_dir, f"{ext[1:].upper()}.svg")
        IconGenerator.create_icon(ext, base_icon, out_path)

    sys.exit(0)
