import sys
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtGui import QPainter, QFont, QColor
from PyQt5.QtCore import QRectF, Qt
from cfg import Static
import os


class Test:

    @classmethod
    def create_generic(cls, file_extension: str):
        renderer = QSvgRenderer(Static.FILE_SVG)
        width = 133
        height = 133

        new_text = file_extension.replace(".", "")[:4]
        new_filename = file_extension.replace(".", "") + ".svg"
        new_path = os.path.join(Static.ICONS_DIR, new_filename)

        # Рисуем на новом SVG с добавлением текста
        painter = QPainter(new_path)
        renderer.render(painter)  # Рисуем SVG
        
        # Добавляем текст
        painter.setPen(QColor(71, 84, 103))  # Цвет текста
        painter.setFont(QFont("Arial", 20, QFont.Bold))
        painter.drawText(QRectF(0, 90, width, 30), Qt.AlignCenter, new_text)
        
        painter.end()

        return new_path
    

    @classmethod
    def create_generic(cls, file_extension: str):

        # открываем стандартную иконку для замены текста
        with open(Static.GENERIC_SVG, "r") as svg_file:
            old_svg_text = svg_file.read()

        # в иконке содержится специальный текст для замены
        replaceable_text = ".EXT"

        # удаляем точку и делаем капслок
        new_text = file_extension.replace(".", "").upper()
        new_svg_text = old_svg_text.replace(replaceable_text, new_text)
        new_filename = file_extension.replace(".", "") + ".svg"
        new_icon_path = os.path.join(
            Static.ICONS_DIR,
            new_filename
            )

        with open(new_icon_path, "w") as svg_file:
            svg_file.write(new_svg_text)

        Static.ICONS_LIST[new_filename] = new_icon_path

        return new_icon_path