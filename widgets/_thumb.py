import datetime
import os
import subprocess

import sqlalchemy
from PyQt5.QtCore import QMimeData, Qt, QUrl, pyqtSignal
from PyQt5.QtGui import QContextMenuEvent, QDrag, QMouseEvent, QPixmap
from PyQt5.QtWidgets import (QAction, QApplication, QFrame, QLabel, QMenu,
                             QSizePolicy, QVBoxLayout)
from sqlalchemy.exc import OperationalError

from cfg import PIXMAP_SIZE, TEXT_LENGTH, THUMB_WIDTH, Config, JsonData
from database import CACHE, Engine
from signals import SIGNALS
from utils import Utils

from .win_info import WinInfo


class NameLabel(QLabel):
    def __init__(self):
        super().__init__()

    def update_name(self, rating: int, colors: str, name: str) -> list[str]:

        max_row = TEXT_LENGTH[JsonData.pixmap_size_ind]

        name_lines = []

        # Проверяем длину текста и обрезаем, если нужно
        if len(name) > max_row:
            first_part = name[:max_row]
            second_part = name[max_row:]

            if len(second_part) > max_row:
                # Обрезаем вторую часть строки с учётом места для троеточия и расширения
                name_start = second_part[:max_row - 10]  # 4 символа расширения + 3 символа перед расширением + 3 для троеточия
                name_end = second_part[-7:]  # 3 символа перед расширением + 4 символа расширения
                second_part = name_start + "..." + name_end

            name = [first_part, second_part]

        # Добавляем рейтинг, если задан
        if rating > 0:
            name_lines.append("\U00002605" * rating)

        # Добавляем цвета, если заданы
        if colors:
            name_lines.append(colors)

        # Добавляем текстовые строки
        if isinstance(name, str):
            name_lines.append(name)
        else:
            name_lines.extend(name[:2])  # Добавляем до 2 строк текста

        # Устанавливаем текст, исключая пустые строки
        self.setText("\n".join(name_lines))


class Thumb(QFrame):
    move_to_wid = pyqtSignal(object)
    clicked = pyqtSignal()

    def __init__(self, src: str, size: int, mod: int, path_to_wid: dict[str, QLabel]):
        super().__init__()
  
        ############################################################
        # path_to_wid для просмотрщика, must_hidden для фильтрации сетки
        self.path_to_wid: dict[str, QLabel] = path_to_wid
        self.src: str = src
        self.must_hidden: bool = False
        ############################################################
        # Данные аттрибуты должны соответстовать ключам в ORDER
        # так как по этим аттрибутам будет совершаться сортировка сетки
        # и фильтрация
        # в Grid ниже будет совершена проверка
        self.name: str = os.path.split(src)[-1]
        self.type: str = os.path.splitext(src)[-1]
        self.size: int = size
        self.mod: int = mod
        self.colors: str = ""
        self.rating: int = 0
        ############################################################
        # для навигации по сетке
        self.row, self.col = 0, 0
        ############################################################
        # при изменении размера мы берем это изображение 210 пикселей
        self.img: QPixmap = None
        ############################################################

        margin = 4

        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(margin, margin, margin, margin)
        v_lay.setSpacing(margin)
        self.setLayout(v_lay)

        self.img_label = QLabel()
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignTop)
        self.img_label.setContentsMargins(margin, margin, margin, margin)
        v_lay.addWidget(self.img_label)

        self.name_label = NameLabel()
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignBottom)
        self.name_label.setContentsMargins(margin, margin, margin, margin)
        v_lay.addWidget(self.name_label)

        self.set_no_frame()
        self.resize()

    # 210 пикселей
    def set_pixmap(self, pixmap: QPixmap):
        self.img = pixmap
        pixmap = Utils.pixmap_scale(pixmap, PIXMAP_SIZE[JsonData.pixmap_size_ind])
        self.img_label.setPixmap(pixmap)

    def resize_pixmap(self):
        if isinstance(self.img, QPixmap):
            pixmap = Utils.pixmap_scale(self.img, PIXMAP_SIZE[JsonData.pixmap_size_ind])
            self.img_label.setPixmap(pixmap)
        else:
            print("thumb has no pixmap in self.img")

    def resize(self):
        if JsonData.name_label_hidden:
            self.img_label.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
            self.name_label.hide()
        else:
            self.img_label.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
            self.name_label.show()

        self.setFixedWidth(THUMB_WIDTH[JsonData.pixmap_size_ind])

        # в update_name меняется длина строки в зависимости от JsonData.thumb_size
        self.name_label.update_name(self.rating, self.colors, self.name)
        self.adjustSize()

    def set_frame(self):
        self.img_label.setStyleSheet(f"background: {Config.GRAY}; border-radius: 4px;")
        self.name_label.setStyleSheet(f"background: {Config.GRAY}; border-radius: 4px;")

    def set_no_frame(self):
        self.img_label.setStyleSheet("")
        self.name_label.setStyleSheet("")

    def add_base_actions(self, context_menu: QMenu):
        view_action = QAction("Просмотр", self)
        view_action.triggered.connect(self.view)
        context_menu.addAction(view_action)

        # Открыть в приложении
        open_menu = QMenu("Открыть в приложении", self)
        context_menu.addMenu(open_menu)

        for name, app_path in Config.image_apps.items():
            wid = QAction(name, parent=open_menu)
            wid.triggered.connect(lambda e, a=app_path: self.open_in_app(a))
            open_menu.addAction(wid)

        context_menu.addSeparator()

        info = QAction("Инфо", self)
        info.triggered.connect(self.show_info_win)
        context_menu.addAction(info)

        # Показать в Finder
        show_in_finder_action = QAction("Показать в Finder", self)
        show_in_finder_action.triggered.connect(self.show_in_finder)
        context_menu.addAction(show_in_finder_action)

        # Скопировать путь до файла
        copy_path = QAction("Скопировать путь до файла", self)
        copy_path.triggered.connect(lambda: Utils.copy_path(self.src))
        context_menu.addAction(copy_path)

        context_menu.addSeparator()

        color_menu = QMenu("Цвета", self)
        context_menu.addMenu(color_menu)

        for color, text in Config.COLORS.items():
            wid = QAction(parent=color_menu, text=f"{color} {text}")
            wid.setCheckable(True)

            if color in self.colors:
                wid.setChecked(True)

            wid.triggered.connect(lambda e, c=color: self.color_click(color_menu, c))
            color_menu.addAction(wid)

        rating_menu = QMenu("Рейтинг", self)
        context_menu.addMenu(rating_menu)

        for rate in range(1, 6):
            wid = QAction(parent=rating_menu, text="\U00002605" * rate)
            wid.setCheckable(True)

            if self.rating == rate:
                wid.setChecked(True)

            wid.triggered.connect(lambda e, r=rate, w=wid: self.rating_click(rating_menu, w, r))
            rating_menu.addAction(wid)

    def show_info_win(self):
        self.win_info = WinInfo(self.get_info())
        Utils.center_win(parent=Utils.get_main_win(), child=self.win_info)
        self.win_info.show()

    def view(self):
        # в win_img_view есть импорт Thumbnail.
        # избегаем circular import
        from .win_img_view import WinImgView
        self.win = WinImgView(self.src, self.path_to_wid)
        Utils.center_win(parent=Utils.get_main_win(), child=self.win)
        self.win.move_to_wid.connect(self.move_to_wid.emit)
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
            self.update_name()

            for item in menu.children():
                item: QAction
                if item.text()[0] in self.colors:
                    item.setChecked(True)

    def get_info(self) -> str:
        _size = round(self.size / (1024**2), 2)
        if _size < 1000:
            f_size = f"{_size} МБ"
        else:
            _size = round(self.size / (1024**3), 2)
            f_size = f"{_size} ГБ"

        rating = "\U00002605" * self.rating

        if self.mod:
            mod = datetime.datetime.fromtimestamp(self.mod).replace(microsecond=0)
            mod = mod.strftime("%d.%m.%Y %H-%M")
        else:
            mod = ""

        text = [
            f"Имя: {self.name}",
            f"Тип: {self.type}" if self.type else f"Тип: папка",
            f"Путь: {self.src}",
            f"Размер: {f_size}" if self.size > 0 else "",
            f"Изменен: {mod}" if mod else "",
            f"Рейтинг: {rating}" if rating else "",
            f"Цвета: {self.colors}" if self.colors else ""
            ]
        text = [i for i in text if i]
        return "\n".join(text)

    def update_name(self):
        self.setToolTip(self.get_info())
        self.name_label.update_name(self.rating, self.colors, self.name)

    def rating_click(self, menu: QMenu, wid: QAction, rate: int):
        if rate == 1:
            rate = 0

        update_db = self.update_data_db(self.colors, rate)

        if update_db:
            self.rating = rate
            self.update_name()

            for i in menu.children():
                i: QAction
                i.setChecked(False)
            if rate > 0:
                wid.setChecked(True)

    def set_colors_from_db(self, colors: str):
        self.colors = colors
        self.update_name()

    def set_rating_from_db(self, rating: int):
        self.rating = rating
        self.update_name()

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
        context_menu = QMenu(self)
        self.add_base_actions(context_menu)
        context_menu.exec_(self.mapToGlobal(a0.pos()))


class ThumbFolder(Thumb):
    def __init__(self, src: str, size: int, mod: int, path_to_wid: dict[str, QLabel]):
        super().__init__(src, size, mod, path_to_wid)

    def fav_cmd(self, offset: int):
        self.fav_action.triggered.disconnect()
        if 0 + offset == 1:
            SIGNALS.add_fav.emit(self.src)
            self.fav_action.setText("Удалить из избранного")
            self.fav_action.triggered.connect(lambda: self.fav_cmd(-1))
        else:
            SIGNALS.del_fav.emit(self.src)
            self.fav_action.setText("Добавить в избранное")
            self.fav_action.triggered.connect(lambda: self.fav_cmd(+1))

    # переназначение метода Thumb
    def view(self):
        SIGNALS.load_standart_grid.emit(self.src)

    def mouseDoubleClickEvent(self, a0: QMouseEvent | None) -> None:
        self.clicked.emit()
        SIGNALS.load_standart_grid.emit(self.src)

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:
        self.clicked.emit()

        context_menu = QMenu(parent=self)

        view_action = QAction("Просмотр", self)
        view_action.triggered.connect(lambda: self.clicked_folder.emit(self.src))
        context_menu.addAction(view_action)

        show_in_finder_action = QAction("Показать в Finder", self)
        show_in_finder_action.triggered.connect(self.show_in_finder)
        context_menu.addAction(show_in_finder_action)

        copy_path = QAction("Скопировать путь до папки", self)
        copy_path.triggered.connect(lambda: Utils.copy_path(self.src))
        context_menu.addAction(copy_path)

        context_menu.addSeparator()

        if self.src in JsonData.favs:
            self.fav_action = QAction("Удалить из избранного", self)
            self.fav_action.triggered.connect(lambda: self.fav_cmd(-1))
            context_menu.addAction(self.fav_action)
        else:
            self.fav_action = QAction("Добавить в избранное", self)
            self.fav_action.triggered.connect(lambda: self.fav_cmd(+1))
            context_menu.addAction(self.fav_action)

        context_menu.exec_(self.mapToGlobal(a0.pos()))

 
class ThumbSearch(Thumb):
    def __init__(self, src: str, size: int, mod: int, path_to_wid: dict[str, QLabel]):
        super().__init__(src, size, mod, path_to_wid)

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:
        self.clicked.emit()
        
        context_menu = QMenu(parent=self)

        self.add_base_actions(context_menu)

        context_menu.addSeparator()

        show_in_folder = QAction("Показать в папке", self)
        show_in_folder.triggered.connect(lambda: SIGNALS.show_in_folder.emit(self.src))
        context_menu.addAction(show_in_folder)

        context_menu.exec_(self.mapToGlobal(a0.pos()))