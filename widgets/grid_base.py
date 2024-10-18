import os
import subprocess

import sqlalchemy
from sqlalchemy.exc import OperationalError
from PyQt5.QtCore import QMimeData, Qt, QUrl, pyqtSignal
from PyQt5.QtGui import QContextMenuEvent, QDrag, QFont, QKeyEvent, QMouseEvent
from PyQt5.QtWidgets import (QAction, QApplication, QFrame, QGridLayout,
                             QLabel, QMenu, QScrollArea, QVBoxLayout, QWidget)

from cfg import Config
from database import CACHE, Engine
from utils import Utils

from .win_rename import WinRename


# Текст с именем файла под изображением
# Максимум 2 строки, дальше прибавляет ...
class NameLabel(QLabel):
    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def update_name(self, rating: int, colors: str, text: str) -> list[str]:
        max_length = 25

        if len(text) > max_length:
            text = text[:max_length] + "..."

        if rating > 0:
            rating = "\U00002605" * rating

        lines = [i for i in (rating, colors, text) if i]

        self.setText("\n".join(lines))


class Geo:
    img_h = Config.img_size
    text_h = 70

    w = Config.img_size + 10
    h = img_h + text_h +10


class Thumbnail(QFrame):
    move_to_wid = pyqtSignal(str)
    clicked = pyqtSignal()
    clicked_folder = pyqtSignal(str)

    def __init__(self, filename: str, src: str, path_to_wid: dict[str: QLabel]):
        super().__init__()
        self.setFixedSize(Geo.w, Geo.h)
        self.src: str = src
        self.path_to_wid: dict[str: QLabel] = path_to_wid
        self.name = filename
        self.colors: str = ""
        self.rating: int = 0

        v_lay = QVBoxLayout()
        v_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v_lay.setContentsMargins(0, 4, 0, 0)
        v_lay.setSpacing(10)
        self.setLayout(v_lay)

        self.img_label = QLabel()
        self.img_label.setFixedHeight(Geo.img_h)
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v_lay.addWidget(self.img_label)

        self.name_label = NameLabel()
        self.name_label.setFixedHeight(Geo.text_h)
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
            wid.triggered.connect(lambda e, a=app_path: self.open_in_app(a))
            open_menu.addAction(wid)

        self.context_menu.addSeparator()

        show_in_finder_action = QAction("Показать в Finder", self)
        show_in_finder_action.triggered.connect(self.show_in_finder)
        self.context_menu.addAction(show_in_finder_action)

        copy_path = QAction("Скопировать путь до файла", self)
        copy_path.triggered.connect(lambda: Utils.copy_path(self.src))
        self.context_menu.addAction(copy_path)

        rename = QAction("Переименовать", self)
        rename.triggered.connect(self.rename_win)
        self.context_menu.addAction(rename)

        self.context_menu.addSeparator()

        self.color_menu = QMenu("Цвета", self)
        self.context_menu.addMenu(self.color_menu)

        for color, text in Config.colors.items():
            wid = QAction(parent=self.color_menu, text=f"{color} {text}")
            wid.setCheckable(True)

            if color in self.colors:
                wid.setChecked(True)

            wid.triggered.connect(lambda e, c=color: self.color_click(c))
            self.color_menu.addAction(wid)

        self.rating_menu = QMenu("Рейтинг", self)
        self.context_menu.addMenu(self.rating_menu)

        for rate in range(1, 6):
            wid = QAction(parent=self.rating_menu, text="\U00002605" * rate)
            wid.setCheckable(True)

            if self.rating == rate:
                wid.setChecked(True)

            wid.triggered.connect(lambda e, r=rate, w=wid: self.rating_click(w, r))
            self.rating_menu.addAction(wid)

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
            # в win_img_view есть импорт Thumbnail.
            # избегаем circular import
            from .win_img_view import WinImgView
            self.win = WinImgView(self.src, self.path_to_wid)
            Utils.center_win(parent=Utils.get_main_win(), child=self.win)
            self.win.move_to_wid.connect(lambda src: self.move_to_wid.emit(src))
            self.win.show()
        else:
            self.clicked_folder.emit(self.src)

    def open_in_app(self, app_path: str):
        subprocess.call(["open", "-a", app_path, self.src])

    def show_in_finder(self):
        subprocess.call(["open", "-R", self.src])

    def color_click(self, color: str):
        if color not in self.colors:
            temp_colors = self.colors + color
        else:
            temp_colors = self.colors.replace(color, "")

        update_db: bool = self.update_data_db(temp_colors, self.rating)

        if update_db:
            self.colors = temp_colors
            key = lambda x: Config.colors_order.index(x)
            self.colors = ''.join(sorted(self.colors, key=key))
            self.name_label.update_name(self.rating, self.colors, self.name)

            for item in self.color_menu.children():
                item: QAction
                if item.text()[0] in self.colors:
                    item.setChecked(True)

    def rating_click(self, wid: QAction, rate: int):
        update_db = self.update_data_db(self.colors, rate)

        if update_db:
            self.name_label.update_name(rate, self.colors, self.name)
            self.rating = rate

            for i in self.rating_menu.children():
                i: QAction
                i.setChecked(False)
            wid.setChecked(True)

    def set_colors(self, colors: str):
        self.colors = colors
        self.name_label.update_name(self.rating, self.colors, self.name)

    def set_rating(self, rating: int):
        self.rating = rating
        self.name_label.update_name(self.rating, self.colors, self.name)

    def update_data_db(self, colors: str, rating: int):
        upd_stmt = sqlalchemy.update(CACHE)
        upd_stmt = upd_stmt.where(CACHE.c.src == self.src).values(colors=colors, rating=rating)

        with Engine.engine.connect() as conn:
            try:
                conn.execute(upd_stmt)
                conn.commit()
            except OperationalError as e:
                Utils.print_error(self, e)
                return False

        return True

    def rename_win(self):
        self.win = WinRename(self.name)
        self.win._finished.connect(self.rename_cmd)
        Utils.center_win(Utils.get_main_win(), self.win)
        self.win.show()

    def rename_cmd(self, text: str):
        root = os.sep + os.path.dirname(self.src).strip(os.sep)
        dest = os.path.join(root, text)
        os.rename(self.src, dest)

        self.name_label.update_name(self.rating, self.colors, text)

        if os.path.isfile(self.src):
            self.path_to_wid.pop(self.src)
            self.path_to_wid[dest] = self

        self.name = text
        self.src  = dest


class Grid(QScrollArea):
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

        self.curr_cell: tuple = (0, 0)
        self.cell_to_wid: dict[tuple: Thumbnail] =  {}
        self.wid_to_cell: dict[Thumbnail: tuple] = {}
        self.path_to_wid: dict[str: Thumbnail] = {}

    def move_to_wid(self, src: str):
        wid = self.path_to_wid.get(src)
        coords = self.wid_to_cell.get(wid)
        if coords:
            self.select_new_widget(coords)

    def select_new_widget(self, coords: tuple):
        new_widget = self.cell_to_wid.get(coords)
        old_widget = self.cell_to_wid.get(self.curr_cell)

        if isinstance(new_widget, QFrame):

            if isinstance(old_widget, QFrame):
                old_widget.setFrameShape(QFrame.Shape.NoFrame)

            new_widget.setFrameShape(QFrame.Shape.Panel)
            self.curr_cell = coords

            self.ensureWidgetVisible(new_widget)

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return):
            wid: Thumbnail = self.cell_to_wid.get(self.curr_cell)
            wid.view()

        elif a0.key() == Qt.Key.Key_Left:
            coords = (self.curr_cell[0], self.curr_cell[1] - 1)
            self.select_new_widget(coords)

        elif a0.key() == Qt.Key.Key_Right:
            coords = (self.curr_cell[0], self.curr_cell[1] + 1)
            self.select_new_widget(coords)

        elif a0.key() == Qt.Key.Key_Up:
            coords = (self.curr_cell[0] - 1, self.curr_cell[1])
            self.select_new_widget(coords)

        elif a0.key() == Qt.Key.Key_Down:
            coords = (self.curr_cell[0] + 1, self.curr_cell[1])
            self.select_new_widget(coords)
        
        return super().keyPressEvent(a0)

    def mouseReleaseEvent(self, a0: QMouseEvent | None) -> None:
        wid = self.cell_to_wid.get(self.curr_cell)
        if isinstance(wid, Thumbnail):
            wid.setFrameShape(QFrame.Shape.NoFrame)
        self.setFocus()
