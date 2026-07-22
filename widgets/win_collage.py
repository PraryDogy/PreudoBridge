from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (QGridLayout, QLabel, QScrollArea, QVBoxLayout,
                             QWidget)

from cfg import JsonData, Static
from system.items import DataItem

from ._base_widgets import UMainWidget


class WinCollage(UMainWidget):
    ww, hh = 700, 700
    title = "Коллаж"

    def __init__(self, data_items: list[DataItem]):
        super().__init__()
        self.set_always_on_top()
        self.set_close_only()
        self.resize(self.ww, self.hh)
        self.setWindowTitle(self.title)

        self.central_layout = QVBoxLayout(self)
        self.central_layout.setContentsMargins(0, 0, 0, 0)

        self.pixmaps: list[QPixmap] = [
            QPixmap.fromImage(i.qimages["src"])
            for i in data_items
        ]
        self.image_labels: list[QLabel] = []

        self.resize_timer = QTimer()
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self.rebuild_grid)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_area.setStyleSheet(
            "QScrollArea { border: none; background-color: black; }"
        )

        self.container = QWidget()
        self.container.setStyleSheet("background-color: black;")
        self.grid_layout = QGridLayout(self.container)
        
        self.grid_layout.setSpacing(10)
        self.grid_layout.setContentsMargins(0, 20, 0, 20)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidget(self.container)
        self.central_layout.addWidget(self.scroll_area)

        self.container.hide()
        self.rebuild_grid()
        self.container.show()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self.resize_timer.isActive():
            self.resize_timer.start(300)

    def rebuild_grid(self):
        while self.grid_layout.count() > 0:
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            widget.deleteLater()
        self.image_labels.clear()

        columns = self.width() // Static.max_thumb_size

        for index, orig_pixmap in enumerate(self.pixmaps):
            row, col = divmod(index, columns)
            label = QLabel()
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setPixmap(orig_pixmap)
            label.setFixedSize(Static.max_thumb_size, Static.max_thumb_size)
            self.grid_layout.addWidget(label, row, col)
            self.image_labels.append(label)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.deleteLater()
        return super().keyPressEvent(event)
