import os
import subprocess

import sqlalchemy
from PyQt5.QtCore import QMimeData, Qt, QUrl, pyqtSignal
from PyQt5.QtGui import QContextMenuEvent, QDrag, QMouseEvent
from PyQt5.QtWidgets import (QAction, QApplication, QFrame, QLabel, QMenu,
                             QVBoxLayout, QWidget)
from sqlalchemy.exc import OperationalError

from cfg import Config, JsonData
from database import CACHE, Engine
from utils import Utils

from .win_rename import WinRename


class NameLabel(QLabel):
    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter)

    def update_name(self, rating: int, colors: str, text: str) -> list[str]:
        max_length = 25

        if len(text) > max_length:
            text = text[:max_length] + "..."

        if rating > 0:
            rating = "\U00002605" * rating

        lines = [i for i in (rating, colors, text) if i]
        # print(lines)
        # lines = []

        self.setText("\n".join(lines))


class Geo:
    img_h = Config.IMG_SIZE
    text_h = 50

    w = Config.IMG_SIZE + 10
    h = img_h + text_h +10


class Thumb(QFrame):
    move_to_wid = pyqtSignal(str)
    clicked = pyqtSignal()

    def __init__(
            self, name: str, size: int, modify: int, type: str, src: str,
            path_to_wid: dict[str, QLabel]
            ):
        super().__init__()
        self.setFixedSize(Geo.w, Geo.h)
        self.path_to_wid: dict[str, QLabel] = path_to_wid
        self.src: str = src

        ############################################################
        # Данные аттрибуты должны соответстовать ключам в ORDER
        # так как по этим аттрибутам будет совершаться сортировка сетки
        # и фильтрация
        # в Grid ниже будет совершена проверка

        self.name = name
        self.size: int = size
        self.modify: int = modify
        self.type: str = type

        self.colors: str = ""
        self.rating: int = 0

        ############################################################

        v_lay = QVBoxLayout()
        v_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v_lay.setContentsMargins(0, 4, 0, 4)
        v_lay.setSpacing(10)
        self.setLayout(v_lay)

        self.img_label = QLabel()
        self.img_label.setFixedHeight(Geo.img_h)
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v_lay.addWidget(self.img_label)

        self.name_label = NameLabel()
        self.name_label.setFixedHeight(Geo.text_h)
        v_lay.addWidget(self.name_label)

        self.context_menu = QMenu(parent=self)

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

        color_menu = QMenu("Цвета", self)
        self.context_menu.addMenu(color_menu)

        for color, text in Config.COLORS.items():
            wid = QAction(parent=color_menu, text=f"{color} {text}")
            wid.setCheckable(True)

            if color in self.colors:
                wid.setChecked(True)

            wid.triggered.connect(lambda e, c=color: self.color_click(color_menu, c))
            color_menu.addAction(wid)

        rating_menu = QMenu("Рейтинг", self)
        self.context_menu.addMenu(rating_menu)

        for rate in range(1, 6):
            wid = QAction(parent=rating_menu, text="\U00002605" * rate)
            wid.setCheckable(True)

            if self.rating == rate:
                wid.setChecked(True)

            wid.triggered.connect(lambda e, r=rate, w=wid: self.rating_click(rating_menu, w, r))
            rating_menu.addAction(wid)

        self.context_menu.exec_(self.mapToGlobal(a0.pos()))

    def view(self):
        # в win_img_view есть импорт Thumbnail.
        # избегаем circular import
        from .win_img_view import WinImgView
        self.win = WinImgView(self.src, self.path_to_wid)
        Utils.center_win(parent=Utils.get_main_win(), child=self.win)
        self.win.move_to_wid.connect(lambda src: self.move_to_wid.emit(src))
        self.win.show()

    def open_in_app(self, app_path: str):
        subprocess.call(["open", "-a", app_path, self.src])

    def show_in_finder(self):
        subprocess.call(["open", "-R", self.src])

    def color_click(self, menu: QMenu, color: str):
        if color not in self.colors:
            temp_colors = self.colors + color
        else:
            temp_colors = self.colors.replace(color, "")

        update_db: bool = self.update_data_db(temp_colors, self.rating)

        if update_db:
            self.colors = temp_colors
            key = lambda x: list(Config.COLORS.keys()).index(x)
            self.colors = ''.join(sorted(self.colors, key=key))
            self.name_label.update_name(self.rating, self.colors, self.name)

            for item in menu.children():
                item: QAction
                if item.text()[0] in self.colors:
                    item.setChecked(True)

    def rating_click(self, menu: QMenu, wid: QAction, rate: int):
        if rate == 1:
            rate = 0

        update_db = self.update_data_db(self.colors, rate)

        if update_db:
            self.name_label.update_name(rate, self.colors, self.name)
            self.rating = rate

            for i in menu.children():
                i: QAction
                i.setChecked(False)
            if rate > 0:
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

    def connect_signals(self, context: QWidget):
        if hasattr(context, ...):
            ...


class ThumbFolder(Thumb):
    add_fav = pyqtSignal(str)
    del_fav = pyqtSignal(str)
    clicked_folder = pyqtSignal(str)

    def __init__(self, name: str, src: str):
        super().__init__(name, 0, 0, "", src, {})
        self.context_menu.clear()

    def mouseDoubleClickEvent(self, a0: QMouseEvent | None) -> None:
        self.clicked.emit()
        self.clicked_folder.emit(self.src)

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:
        self.clicked.emit()

        view_action = QAction("Просмотр", self)
        view_action.triggered.connect(lambda: self.clicked_folder.emit(self.src))
        self.context_menu.addAction(view_action)

        self.context_menu.addSeparator()

        show_in_finder_action = QAction("Показать в Finder", self)
        show_in_finder_action.triggered.connect(self.show_in_finder)
        self.context_menu.addAction(show_in_finder_action)

        copy_path = QAction("Скопировать путь до папки", self)
        copy_path.triggered.connect(lambda: Utils.copy_path(self.src))
        self.context_menu.addAction(copy_path)

        rename = QAction("Переименовать", self)
        rename.triggered.connect(self.rename_win)
        self.context_menu.addAction(rename)

        self.context_menu.addSeparator()

        if self.src in JsonData.favs:
            self.fav_action = QAction("Удалить из избранного", self)
            self.fav_action.triggered.connect(lambda: self.fav_cmd(-1))
            self.context_menu.addAction(self.fav_action)
        else:
            self.fav_action = QAction("Добавить в избранное", self)
            self.fav_action.triggered.connect(lambda: self.fav_cmd(+1))
            self.context_menu.addAction(self.fav_action)

        self.context_menu.exec_(self.mapToGlobal(a0.pos()))

    def fav_cmd(self, offset: int):
        self.fav_action.triggered.disconnect()
        if 0 + offset == 1:
            self.add_fav.emit(self.src)
            self.fav_action.setText("Удалить из избранного")
            self.fav_action.triggered.connect(lambda: self.fav_cmd(-1))
        else:
            self.del_fav.emit(self.src)
            self.fav_action.setText("Добавить в избранное")
            self.fav_action.triggered.connect(lambda: self.fav_cmd(+1))

    def view(self):
        self.clicked_folder.emit(self.src)

class ThumbSearch(Thumb):
    show_in_folder = pyqtSignal(str)

    def __init__(self, name: str, src: str, path_to_wid: dict[str: Thumb]):
        super().__init__(name, 0, 0, "", src, path_to_wid)

        show_in_folder = QAction("Показать в папке", self)
        show_in_folder.triggered.connect(lambda: self.show_in_folder.emit(self.src))
        self.context_menu.addAction(show_in_folder)

        self.context_menu.addSeparator()