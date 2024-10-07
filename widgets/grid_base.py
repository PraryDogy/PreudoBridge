import os
import subprocess
from typing import Union

from PyQt5.QtCore import QMimeData, Qt, QUrl, pyqtSignal
from PyQt5.QtGui import QContextMenuEvent, QDrag, QKeyEvent, QMouseEvent
from PyQt5.QtWidgets import (QAction, QApplication, QFrame, QGridLayout,
                             QLabel, QMenu, QScrollArea, QVBoxLayout, QWidget)

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
    _clicked_sig = pyqtSignal()

    def __init__(self, filename: str, src: str, paths: list):
        super().__init__()
        self.setFixedSize(250, 280)
        self.src: str = src
        self.paths: list = paths

        self.setFrameShape(QFrame.Shape.NoFrame)
        tooltip = filename + "\n" + src
        self.setToolTip(tooltip)

        v_lay = QVBoxLayout()
        v_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        self._clicked_sig.emit()

    def mousePressEvent(self, a0: QMouseEvent | None) -> None:
        if a0.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = a0.pos()

    def mouseMoveEvent(self, a0: QMouseEvent | None) -> None:
        if a0.button() == Qt.MouseButton.RightButton:
            return
        
        try:
            distance = (a0.pos() - self.drag_start_position).manhattanLength()
        except AttributeError:
            return

        if distance < QApplication.startDragDistance():
            return

        self._clicked_sig.emit()

        self.drag = QDrag(self)
        self.mime_data = QMimeData()
        self.drag.setPixmap(self.img_label.pixmap())
        
        url = [QUrl.fromLocalFile(self.src)]
        self.mime_data.setUrls(url)

        self.drag.setMimeData(self.mime_data)
        self.drag.exec_(Qt.DropAction.CopyAction)

    def mouseDoubleClickEvent(self, a0: QMouseEvent | None) -> None:
        if a0.button() == Qt.MouseButton.LeftButton:
            self._clicked_sig.emit()
            self.win = WinImgView(self.src, self.paths)
            Utils.center_win(parent=Utils.get_main_win(), child=self.win)
            self.win.closed.connect(lambda src: self._move_to_wid_sig.emit(src))
            self.win.show()

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:
        self._clicked_sig.emit()
        self.context_menu.exec_(self.mapToGlobal(a0.pos()))

    def _view_file(self):
        if self.src.endswith(Config.img_ext):
            self.win = WinImgView(self.src, self.paths)
            self.win.closed.connect(lambda src: self._move_to_wid_sig.emit(src))
            main_win = Utils.get_main_win()
            Utils.center_win(parent=main_win, child=self.win)
            self.win.show()

    def _open_default(self):
        subprocess.call(["open", self.src])

    def _show_in_finder(self):
        subprocess.call(["open", "-R", self.src])


class EmptyThumbnail:
    def setFrameShape(*args, **kwargs):
        ...


class Grid(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        Config.image_grid_widgets_global.clear()

        main_wid = QWidget()
        self.grid_layout = QGridLayout(main_wid)
        self.grid_layout.setSpacing(5)
        self.setWidget(main_wid)
        
        self._row_col_widget: dict[tuple: Thumbnail] = {} # (строка, колонка): виджет
        self._path_widget: dict[str: Thumbnail] = {} # путь к фото: виджет
        self._widget_row_col: dict[Thumbnail: tuple] = {} # виджет: (строка, колонка)
        self._widget_path: dict[Thumbnail: str] = {} # виджет: путь к фото
        self._paths: list = [] # Список путей к изображениям в сетке

        self._selected_thumbnail: Thumbnail = EmptyThumbnail() # Какой виджет сейчас выделен
        self.cur_row: int = 0
        self.cur_col: int = 0
        self.row_count: int = 1
        self.col_count: int = 1

    def _move_to_wid(self, src: str):
        try:
            wid: Thumbnail = self._path_widget.get(src)
            wid._clicked_sig.emit()
            self.ensureWidgetVisible(wid)
        except (RuntimeError, KeyError) as e:
            print("move to wid error: ", e)

    def _frame_selected_widget(self, shape: QFrame.Shape):
        try:
            self._selected_thumbnail.setFrameShape(shape)
            self.ensureWidgetVisible(self._selected_thumbnail)
        except (AttributeError, TypeError):
            pass

    def _add_wid_to_dicts(self, data: dict):
        """row, col, widget, src"""
        self._row_col_widget[(data.get("row"), data.get("col"))] = data.get("widget")
        self._widget_row_col[data.get("widget")] = (data.get("row"), data.get("col"))
        self._path_widget[data.get("src")] = data.get("widget")
        self._widget_path[data.get("widget")] = data.get("src")

        if os.path.isfile(data.get("src")):
            self._paths.append(data.get("src"))

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:

        if a0.key() == Qt.Key.Key_Space:
            self._selected_thumbnail._view_file()

        elif a0.key() == Qt.Key.Key_Left:
            self._frame_selected_widget(QFrame.Shape.NoFrame)
            self.cur_col = 0 if self.cur_col == 0 else self.cur_col - 1
            self._selected_thumbnail = self._row_col_widget.get((self.cur_row, self.cur_col))
            self._frame_selected_widget(QFrame.Shape.Panel)

        elif a0.key() == Qt.Key.Key_Right:
            self._frame_selected_widget(QFrame.Shape.NoFrame)
            self.cur_col = self.col_count if self.cur_col == self.col_count else self.cur_col + 1 
            self._selected_thumbnail = self._row_col_widget.get((self.cur_row, self.cur_col))
            self._frame_selected_widget(QFrame.Shape.Panel)

        elif a0.key() == Qt.Key.Key_Up:
            self._frame_selected_widget(QFrame.Shape.NoFrame)
            self.cur_row = 0 if self.cur_row == 0 else self.cur_row - 1
            self._selected_thumbnail = self._row_col_widget.get((self.cur_row, self.cur_col))
            self._frame_selected_widget(QFrame.Shape.Panel)

        elif a0.key() == Qt.Key.Key_Down:
            self._frame_selected_widget(QFrame.Shape.NoFrame)
            self.cur_row = self.row_count if self.cur_row == self.row_count else self.cur_row + 1
            self._selected_thumbnail = self._row_col_widget.get((self.cur_row, self.cur_col))
            self._frame_selected_widget(QFrame.Shape.Panel)

    def mouseReleaseEvent(self, a0: QMouseEvent | None) -> None:
        self._frame_selected_widget(QFrame.Shape.NoFrame)


class GridMethods:
    def resize_grid(self) -> None:
        raise NotImplementedError("Переназначь resize_grid")

    def stop_and_wait_threads(self) -> None:
        raise NotImplementedError("Переназначь stop_and_wait_threads")

    def sort_grid(self) -> None:
        raise NotImplementedError("Переназначь sort_grid")

    def move_to_wid(self) -> None:
        raise NotImplementedError("Переназначь move_to_wid")
