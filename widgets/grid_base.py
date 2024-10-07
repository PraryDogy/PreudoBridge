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


# Текст с именем файла под изображением
# Максимум 2 строки, дальше прибавляет ...
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


# Базовый виджет для файлов, сверху фото, снизу имя файла
# Контекстное меню заранее определено, можно добавить пункты
# Весь виджет можно перетаскивать мышкой на графические редакторы (Photoshop)
# В редактор переместится только изображение
# В случае, когда виджет назначается на папку, скопируется вся папка на жесткий диск
# Двойной клик открывает просмотрщик изображений
class Thumbnail(QFrame):
    # просмотрщик изображений был закрыт и в аргумент передается путь к
    # фотографии, на которой просмотрщик остановился
    _move_to_wid_sig = pyqtSignal(str)

    # по виджету произошел любой клик мыши (правый левый неважно)
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
        v_lay.setSpacing(10)
        self.setLayout(v_lay)

        self.img_label = QLabel()
        self.img_label.setFixedHeight(Config.thumb_size)
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v_lay.addWidget(self.img_label)

        filename = os.path.basename(src)
        img_name = NameLabel(filename)
        v_lay.addWidget(img_name)


        # КОНЕКСТНОЕ МЕНЮ
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


# Заглушка
# При первой инициации Grid - _selected_thumbnail является None
# И чтобы не осуществлять проверку на None, мы добавляем эту заглушку
# С теми же методами, что и в Thumbnail
class EmptyThumbnail:
    def setFrameShape(*args, **kwargs):
        ...
    
    def _view_file(*args, **kwargs):
        ...


# Методы для внешнего использования, которые обязательно нужно
# переназначить в наследнике Grid, потому что в GUI идет обращение
# к этим методам без разбора
# полиморфизм
class GridMethods:
    def resize_grid(self) -> None:
        raise NotImplementedError("Переназначь resize_grid")

    def stop_and_wait_threads(self) -> None:
        raise NotImplementedError("Переназначь stop_and_wait_threads")

    def sort_grid(self) -> None:
        raise NotImplementedError("Переназначь sort_grid")


# Сетка изображений
class Grid(QScrollArea, GridMethods):
    def __init__(self, width: int):
        super().__init__()
        self.setWidgetResizable(True)

        main_wid = QWidget()
        self.grid_layout = QGridLayout(main_wid)
        self.grid_layout.setSpacing(5)
        self.setWidget(main_wid)

        ############################################################

        # С помощью данных словарей мы упрощаем навигацию по сетке
        # зображений клавиатурными стрелочками
        # чтобы каждый раз не итерировать и не искать, какой виджет был выделен,
        # а какой нужно выделить теперь

        ############################################################

        # Поиск виджета по номеру строки и колонки
        # При нажатии на клавиатурную стрелочку мы знаем новую строку и колонку
        # (строка, колонка): виджет
        self._row_col_widget: dict[tuple: Thumbnail] = {}

        # Поиск виджета по пути к изображению
        # Когда просмотрщик закрывается и Thumbnail посылает сигнал
        # move_to_wid в сетку, в аргументе сигнала содержится путь к изображению
        # и мы ищем по этому пути, на каком виджете с изображением остановился
        # просмотр, чтобы перевести на него выделение и скролл
        # Используется в Grid._move_to_wid
        # путь к фото: виджет
        self._path_widget: dict[str: Thumbnail] = {}

        # Поиск номера строки и колонки по виджету
        # Клик мышкой по Thumbnail и мы узнаем строку и колонку
        # Если дальнейшую навигацию по сетке осуществлять клавишами
        # то важно знать, какая сейчас строка и колонка выделена
        # Используется в _clicked_thumb во всех наследниках Grid
        # виджет: (строка, колонка). 
        self._widget_row_col: dict[Thumbnail: tuple] = {}


        # Список путей к изображениям в сетке, который передается в
        # просмотрщик изображений
        self._paths: list = []

        # Текущий выделенный виджет
        # Когда происходит клик вне виджета или по другому виджету Thumbnail
        # С данного виджета снимается выделение
        self._cur_thumb: Thumbnail = EmptyThumbnail()
        self._cur_row: int = 0
        self._cur_col: int = 0

        # Максимальное количество строк
        # При итерации изображений в сетке, каждый раз прибавляется + 1
        self.row_count: int = 0

        # Макимальное количество колонок
        self.col_count = Utils.get_clmn_count(width)

    def _frame_selected_widget(self, shape: QFrame.Shape):
        try:
            self._cur_thumb.setFrameShape(shape)
            self.ensureWidgetVisible(self._cur_thumb)
        except (AttributeError, TypeError) as e:
            pass

    # Общий метод для всех Grid
    # В каждой Grud сигнал каждого Thumbnail - _move_to_wid_sig
    # мы подключаем к данному методу
    def _move_to_wid_cmd(self, src: str):
        try:
            wid: Thumbnail = self._path_widget.get(src)
            wid._clicked_sig.emit()
            self.ensureWidgetVisible(wid)
        except (RuntimeError, KeyError) as e:
            print("move to wid error: ", e)

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() == Qt.Key.Key_Space:
            self._cur_thumb._view_file()

        elif a0.key() == Qt.Key.Key_Left:
            self._frame_selected_widget(QFrame.Shape.NoFrame)
            self._cur_col = 0 if self._cur_col == 0 else self._cur_col - 1
            self._cur_thumb = self._row_col_widget.get((self._cur_row, self._cur_col))
            self._frame_selected_widget(QFrame.Shape.Panel)

        elif a0.key() == Qt.Key.Key_Right:
            self._frame_selected_widget(QFrame.Shape.NoFrame)
            self._cur_col = self.col_count - 1 if self._cur_col == self.col_count - 1 else self._cur_col + 1 
            self._cur_thumb = self._row_col_widget.get((self._cur_row, self._cur_col))
            self._frame_selected_widget(QFrame.Shape.Panel)

        elif a0.key() == Qt.Key.Key_Up:
            self._frame_selected_widget(QFrame.Shape.NoFrame)
            self._cur_row = 0 if self._cur_row == 0 else self._cur_row - 1
            self._cur_thumb = self._row_col_widget.get((self._cur_row, self._cur_col))
            self._frame_selected_widget(QFrame.Shape.Panel)

        elif a0.key() == Qt.Key.Key_Down:
            self._frame_selected_widget(QFrame.Shape.NoFrame)
            self._cur_row = self.row_count if self._cur_row == self.row_count else self._cur_row + 1
            self._cur_thumb = self._row_col_widget.get((self._cur_row, self._cur_col))
            self._frame_selected_widget(QFrame.Shape.Panel)

    def mouseReleaseEvent(self, a0: QMouseEvent | None) -> None:
        self._frame_selected_widget(QFrame.Shape.NoFrame)
