import io
import subprocess

import cv2
import numpy as np
from PyQt5.QtCore import QByteArray
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QApplication, QVBoxLayout, QWidget


class Utils:
    @staticmethod
    def clear_layout(layout: QVBoxLayout):
        if layout:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
                else:
                    Utils.clear_layout(item.layout())

    @staticmethod
    def copy_path(text: str):
        text_bytes = text.encode('utf-8')
        subprocess.run(['pbcopy'], input=text_bytes, check=True)
        return True
    
    @staticmethod
    def get_main_win(name: str ="SimpleFileExplorer") -> QWidget:
        for i in QApplication.topLevelWidgets():
            if name in str(i):
                return i
    @staticmethod
    def center_win(parent: QWidget, child: QWidget):
        geo = child.geometry()
        geo.moveCenter(parent.geometry().center())
        child.setGeometry(geo)


class PixmapFromBytes(QPixmap):
    def __init__(self, byte_array: QByteArray) -> QPixmap:
        super().__init__()

        ba = QByteArray(byte_array)
        self.loadFromData(ba, "JPEG")


class DbImage(io.BytesIO):
    def __init__(self, image: np.ndarray) -> io.BytesIO:
        super().__init__()
        img = np.array(image)
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        res, buffer = cv2.imencode(".jpeg", img)
        self.write(buffer)
