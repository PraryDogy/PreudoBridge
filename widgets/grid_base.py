import os

from PyQt5.QtCore import QMimeData, Qt, QThread, QTimer, QUrl, pyqtSignal
from PyQt5.QtGui import (QCloseEvent, QContextMenuEvent, QDrag, QKeyEvent,
                         QMouseEvent, QPixmap)
from PyQt5.QtWidgets import (QAction, QApplication, QFrame, QGridLayout,
                             QLabel, QMenu, QScrollArea, QSizePolicy,
                             QSpacerItem, QVBoxLayout, QWidget)

from cfg import Config
from utils import Utils


class NameLabel(QLabel):
    def __init__(self, filename: str):
        super().__init__()
        self.setText(self.split_text(filename))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def split_text(self, text: str) -> list[str]:
        max_length = 27
        lines = []
        
        while len(text) > max_length:
            lines.append(text[:max_length])
            text = text[max_length:]

        if text:
            lines.append(text)

        if len(lines) > 2:
            lines = lines[:2]
            lines[-1] = lines[-1][:max_length-3] + '...'

        return "\n".join(lines)


class Thumbnail(QFrame):
    def __init__(self, filename: str, src: str):
        super().__init__()
        self.setFixedSize(250, 280)
        self.src = src

        self.setFrameShape(QFrame.Shape.NoFrame)
        tooltip = filename + "\n" + src
        self.setToolTip(tooltip)

        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(0, 0, 0, 0)
        v_lay.setSpacing(0)
        self.setLayout(v_lay)

        self.img_label = QLabel()
        self.img_label.setFixedHeight(Config.thumb_size)
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v_lay.addWidget(self.img_label)

        filename = os.path.basename(src)
        img_name = NameLabel(filename)
        v_lay.addWidget(img_name)

    def mouseReleaseEvent(self, a0: QMouseEvent | None) -> None:
        self.select_thumbnail()
        return super().mouseReleaseEvent(a0)

    def mousePressEvent(self, a0: QMouseEvent | None) -> None:
        if a0.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = a0.pos()
        return super().mousePressEvent(a0)

    def mouseMoveEvent(self, a0: QMouseEvent | None) -> None:
        if a0.button() == Qt.MouseButton.RightButton:
            return
        
        try:
            distance = (a0.pos() - self.drag_start_position).manhattanLength()
        except AttributeError:
            return

        if distance < QApplication.startDragDistance():
            return

        self.select_thumbnail()

        self.drag = QDrag(self)
        self.mime_data = QMimeData()
        self.drag.setPixmap(self.img_label.pixmap())
        
        url = [QUrl.fromLocalFile(self.src)]
        self.mime_data.setUrls(url)

        self.drag.setMimeData(self.mime_data)
        self.drag.exec_(Qt.DropAction.CopyAction)
        return super().mouseMoveEvent(a0)
    
    def select_thumbnail(self):
        Utils.deselect_selected_thumb()
        self.setFrameShape(QFrame.Shape.Panel)
        Config.selected_thumbnail = self        



class GridMethods:
    def rearrange(self) -> None: ...
    def stop_and_wait_threads(self) -> None: ...
    def rearrange_sorted(self) -> None: ...