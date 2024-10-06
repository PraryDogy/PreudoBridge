import os
import subprocess

from PyQt5.QtCore import QMimeData, Qt, QThread, QTimer, QUrl, pyqtSignal
from PyQt5.QtGui import (QCloseEvent, QContextMenuEvent, QDrag, QKeyEvent,
                         QMouseEvent, QPixmap)
from PyQt5.QtWidgets import (QAction, QApplication, QFrame, QGridLayout,
                             QLabel, QMenu, QScrollArea, QSizePolicy,
                             QSpacerItem, QVBoxLayout, QWidget)

from cfg import Config
from utils import Utils

from .win_img_view import WinImgView


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
    _move_to_wid_sig = pyqtSignal(str)

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

        self.context_menu = QMenu(self)

        view_action = QAction("Просмотр", self)
        view_action.triggered.connect(self._view_file)
        self.context_menu.addAction(view_action)

        self.context_menu.addSeparator()

        open_action = QAction("Открыть по умолчанию", self)
        open_action.triggered.connect(self._open_default)
        self.context_menu.addAction(open_action)

        show_in_finder_action = QAction("Показать в Finder", self)
        show_in_finder_action.triggered.connect(self._show_in_finder)
        self.context_menu.addAction(show_in_finder_action)

        copy_path = QAction("Скопировать путь до файла", self)
        copy_path.triggered.connect(lambda: Utils.copy_path(self.src))
        self.context_menu.addAction(copy_path)

    def mouseReleaseEvent(self, a0: QMouseEvent | None) -> None:
        self.select_thumbnail()

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

    def mouseDoubleClickEvent(self, a0: QMouseEvent | None) -> None:
        if a0.button() == Qt.MouseButton.LeftButton:
            self.select_thumbnail()
            self.win = WinImgView(self, self.src)
            Utils.center_win(parent=Utils.get_main_win(), child=self.win)
            self.win.closed.connect(lambda src: self._move_to_wid_sig.emit(src))
            self.win.show()

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:
        self.select_thumbnail()
        self.context_menu.exec_(self.mapToGlobal(a0.pos()))

    def _view_file(self):
        if self.src.endswith(Config.img_ext):
            self.win = WinImgView(self, self.src)
            self.win.closed.connect(lambda src: self._move_to_wid_sig.emit(src))
            main_win = Utils.get_main_win()
            Utils.center_win(parent=main_win, child=self.win)
            self.win.show()

    def _open_default(self):
        subprocess.call(["open", self.src])

    def _show_in_finder(self):
        subprocess.call(["open", "-R", self.src])

    def select_thumbnail(self):
        try:
            wid: QFrame = Config.selected_thumbnail
            wid.setFrameShape(QFrame.Shape.NoFrame)
        except (RuntimeError, AttributeError) as e:
            print("thumbnail > deselect prev thumb error:", e)

        self.setFrameShape(QFrame.Shape.Panel)
        Config.selected_thumbnail = self        


class GridMethods:
    def rearrange(self) -> None: ...
    def stop_and_wait_threads(self) -> None: ...
    def rearrange_sorted(self) -> None: ...

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() == Qt.Key.Key_Space:

            wid: Thumbnail = Config.selected_thumbnail
            if os.path.isdir(self.src):
                wid._view_file()
