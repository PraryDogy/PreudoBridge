from PyQt5.QtWidgets import QListWidget, QListWidgetItem, QLabel
from PyQt5.QtCore import Qt, pyqtSignal
import os

class TreeFavorites(QListWidget):
    on_fav_clicked = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        mac = "/Volumes/Macintosh HD"
        desktop = mac + os.path.join(os.path.expanduser('~'), 'Desktop')
        downloads = mac + os.path.join(os.path.expanduser('~'), 'Downloads')
        self.add_item("Рабочий стол", desktop)
        self.add_item("Загрузки", downloads)

    def add_item(self, name: str, src: str):
        wid = QLabel(text=name)
        wid.setStyleSheet("padding-left: 5px;")
        wid.setFixedHeight(25)
        list_item = QListWidgetItem()
        list_item.setSizeHint(wid.sizeHint())

        self.addItem(list_item)
        self.setItemWidget(list_item, wid)

        wid.mouseReleaseEvent = lambda e: self.on_fav_clicked.emit(src)