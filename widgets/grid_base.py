import os
import subprocess

import sqlalchemy
from PyQt5.QtCore import QMimeData, Qt, QUrl, pyqtSignal
from PyQt5.QtGui import QContextMenuEvent, QDrag, QKeyEvent, QMouseEvent
from PyQt5.QtWidgets import (QAction, QApplication, QFrame, QGridLayout,
                             QLabel, QMenu, QScrollArea, QVBoxLayout, QWidget)

from cfg import Config
from database import Cache, Dbase
from utils import Utils

from .win_img_view import WinImgView


# Текст с именем файла под изображением
# Максимум 2 строки, дальше прибавляет ...
class NameLabel(QLabel):
    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_text(self, text: str) -> list[str]:
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

        self.setText("\n".join(lines))


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

    # !!!!!!!! при переназначении клик эвентов не забудь добавить _clicked_sig
    # по виджету произошел любой клик мыши (правый левый неважно)
    clicked = pyqtSignal()
    clicked_folder = pyqtSignal(str)

    def __init__(self, filename: str, src: str, paths: list):
        super().__init__()
        self.setFixedSize(250, 280)
        self.src: str = src
        self.paths: list = paths
        self.filename = filename
        self.colors: str = ""
        self.colored_filename = self.colors + "\n" + filename

        self.setFrameShape(QFrame.Shape.NoFrame)
        tooltip = self.filename + "\n" + src
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

        self.name_label = NameLabel()
        self.name_label.set_text(self.colored_filename)
        v_lay.addWidget(self.name_label)

        # КОНЕКСТНОЕ МЕНЮ
        self.context_menu = QMenu(self)

        view_action = QAction("Просмотр", self)
        view_action.triggered.connect(self.view)
        self.context_menu.addAction(view_action)


        open_menu = QMenu("Открыть в приложении", self)
        self.context_menu.addMenu(open_menu)

        for name, app_path in Config.image_apps.items():
            wid = QAction(name, parent=open_menu)
            wid.triggered.connect(lambda e, a=app_path: self._open_default(a))
            open_menu.addAction(wid)

        self.context_menu.addSeparator()

        show_in_finder_action = QAction("Показать в Finder", self)
        show_in_finder_action.triggered.connect(self._show_in_finder)
        self.context_menu.addAction(show_in_finder_action)

        copy_path = QAction("Скопировать путь до файла", self)
        copy_path.triggered.connect(lambda: Utils.copy_path(self.src))
        self.context_menu.addAction(copy_path)

        self.context_menu.addSeparator()

        color_menu = QMenu("Цвета", self)
        self.context_menu.addMenu(color_menu)
        self.color_items = []

        for color, text in Config.colors.items():
            wid = QAction(parent=color_menu, text=f"{color} {text}")
            wid.setCheckable(True)
            self.color_items.append(wid)

            if color in self.colors:
                wid.setChecked(True)

            wid.triggered.connect(lambda e, c=color: self.color_click(c))
            color_menu.addAction(wid)

    def mouseReleaseEvent(self, a0: QMouseEvent | None) -> None:
        self.clicked.emit()

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

        self.clicked.emit()

        self.drag = QDrag(self)
        self.mime_data = QMimeData()
        self.drag.setPixmap(self.img_label.pixmap())
        
        url = [QUrl.fromLocalFile(self.src)]
        self.mime_data.setUrls(url)

        self.drag.setMimeData(self.mime_data)
        self.drag.exec_(Qt.DropAction.CopyAction)

    def mouseDoubleClickEvent(self, a0: QMouseEvent | None) -> None:
        if a0.button() == Qt.MouseButton.LeftButton:
            self.view()

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:
        self.clicked.emit()
        self.context_menu.exec_(self.mapToGlobal(a0.pos()))

    def view(self):
        if os.path.isfile(self.src):
            self.win = WinImgView(self.src, self.paths)
            Utils.center_win(parent=Utils.get_main_win(), child=self.win)
            self.win.closed.connect(lambda src: self._move_to_wid_sig.emit(src))
            self.win.show()
        else:
            self.clicked_folder.emit(self.src)

    def _open_default(self, app_path: str):
        subprocess.call(["open", "-a", app_path, self.src])

    def _show_in_finder(self):
        subprocess.call(["open", "-R", self.src])

    def color_click(self, color: str):
        if color not in self.colors:
            self.colors = self.colors + color
        else:
            self.colors.replace(color, "")

        self.update_colors(self.colors)
        self.color_to_db()

    def color_to_db(self):
        sess = Dbase.get_session()
        q = sqlalchemy.update(Cache)
        q = q.where(Cache.src==self.src)
        q = q.values({"colors": "".join(self.colors)})
        try:
            sess.execute(q)
            sess.commit()
        except Exception as e:
            print(e)
        sess.close()

    def update_colors(self, colors: str):
        self.colors = colors
        self.colors = ''.join(sorted(self.colors, key=lambda x: Config.colors_order.index(x)))

        self.colored_filename = self.colors + "\n" + self.filename
        self.name_label.set_text(self.colored_filename)

        for item in self.color_items:
            item: QAction
            if item.text()[0] in self.colors:
                item.setChecked(True)

# Методы для внешнего использования, которые обязательно нужно
# переназначить в наследнике Grid, потому что в GUI идет обращение
# к этим методам без разбора
# полиморфизм
class GridMethods:
    def __init__(self):
        super().__init__()

    def resize_grid(self) -> None:
        raise NotImplementedError("Переназначь resize_grid")

    def stop_and_wait_threads(self) -> None:
        raise NotImplementedError("Переназначь stop_and_wait_threads")

    def sort_grid(self) -> None:
        raise NotImplementedError("Переназначь sort_grid")

    def move_to_wid(self, path: str):
        raise NotImplementedError("Переназначь move_to_wid")


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

        # координаты: строка, столбец
        # при формировании сетки наполняется словарь coords
        # reversed это value: key - coords
        # все это для навигации по сетке

        ############################################################

        self.coords_cur = (0, 0)
        self.coords: dict[tuple: Thumbnail] =  {}
        self.coords_reversed: dict[Thumbnail: tuple] = {}

        self._paths_widgets: dict[str: Thumbnail] = {}
        self._paths_images: list = []

    # Общий метод для всех Grid
    # В каждой Grud сигнал каждого Thumbnail - _move_to_wid_sig
    # мы подключаем к данному методу
    def _move_to_wid_cmd(self, src: str):
        try:
            wid: Thumbnail = self._paths_widgets.get(src)
            wid.clicked.emit()
            self.ensureWidgetVisible(wid)
        except (RuntimeError, KeyError) as e:
            print("move to wid error: ", e)

    def select_new_widget(self, coords: tuple):
        new_widget = self.coords.get(coords)
        old_widget = self.coords.get(self.coords_cur)

        if isinstance(new_widget, QFrame):

            if isinstance(old_widget, QFrame):
                old_widget.setFrameShape(QFrame.Shape.NoFrame)

            new_widget.setFrameShape(QFrame.Shape.Panel)
            self.coords_cur = coords

            self.ensureWidgetVisible(new_widget)

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return):
            wid: Thumbnail = self.coords.get(self.coords_cur)
            wid.view()

        elif a0.key() == Qt.Key.Key_Left:
            coords = (self.coords_cur[0], self.coords_cur[1] - 1)
            self.select_new_widget(coords)

        elif a0.key() == Qt.Key.Key_Right:
            coords = (self.coords_cur[0], self.coords_cur[1] + 1)
            self.select_new_widget(coords)

        elif a0.key() == Qt.Key.Key_Up:
            coords = (self.coords_cur[0] - 1, self.coords_cur[1])
            self.select_new_widget(coords)

        elif a0.key() == Qt.Key.Key_Down:
            coords = (self.coords_cur[0] + 1, self.coords_cur[1])
            self.select_new_widget(coords)
        
        return super().keyPressEvent(a0)

    def mouseReleaseEvent(self, a0: QMouseEvent | None) -> None:
        wid = self.coords.get(self.coords_cur)
        if isinstance(wid, Thumbnail):
            wid.setFrameShape(QFrame.Shape.NoFrame)
        self.setFocus()