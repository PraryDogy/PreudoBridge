import datetime
import subprocess

import sqlalchemy
from PyQt5.QtCore import QMimeData, Qt, QUrl, pyqtSignal
from PyQt5.QtGui import QContextMenuEvent, QDrag, QMouseEvent, QPixmap
from PyQt5.QtWidgets import (QAction, QApplication, QFrame, QLabel, QMenu,
                             QVBoxLayout)
from sqlalchemy.exc import OperationalError

from cfg import (COLORS, GRAY, IMAGE_APPS, MARGIN, PIXMAP_SIZE, TEXT_LENGTH,
                 THUMB_W, JsonData)
from database import CACHE, Engine, OrderItem
from signals import SIGNALS
from utils import Utils

from .win_info import WinInfo


class NameLabel(QLabel):
    star = "\U00002605"

    def __init__(self):
        super().__init__()

    def set_text(self, wid: OrderItem) -> list[str]:
        name: str | list = wid.name

        # Максимальная длина строки исходя из ширины pixmap в Thumb
        max_row = TEXT_LENGTH[JsonData.pixmap_size_ind]
        
        # Разбиение имени на строки в зависимости от длины
        if len(name) > max_row:
            if wid.rating > 0:
                # Если есть цветные теги, имя в одну строку
                name = [f"{name[:max_row - 10]}...{name[-7:]}"]
            else:
                # Иначе имя может быть в 2 строки
                first_part = name[:max_row]
                second_part = name[max_row:]
                
                if len(second_part) > max_row:
                    second_part = f"{second_part[:max_row - 10]}...{second_part[-7:]}"
                
                name = [first_part, second_part]
        else:
            name = [name]

        if wid.rating > 0:
            name.append(self.star * wid.rating)

        self.setText("\n".join(name))


class ColorLabel(QLabel):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("font-size: 9px;")

    def set_text(self, wid: OrderItem):
        self.setText(wid.colors)


class Thumb(OrderItem, QFrame):
    clicked = pyqtSignal()

    def __init__(
            self,
            src: str,
            size: int = None,
            mod: int = None,
            colors: str = None,
            rating: int = None,
            pixmap: QPixmap = None,
            path_to_wid: dict[str, QLabel] = None
            ):

        QFrame.__init__(self, parent=None)
        OrderItem.__init__(self, src=src, size=size, mod=mod, colors=colors, rating=rating)

        self.img: QPixmap = pixmap
        self.must_hidden: bool = False
        self.path_to_wid: dict[str, QLabel] = {} if path_to_wid is None else path_to_wid
        self.row, self.col = 0, 0

        size_ = round(self.size / (1024**2), 2)
        if size_ < 1000:
            self.f_size = f"{size_} МБ"
        else:
            size_ = round(self.size / (1024**3), 2)
            self.f_size = f"{size_} ГБ"

        if self.mod:
            str_date = datetime.datetime.fromtimestamp(self.mod).replace(microsecond=0)
            self.f_mod: str = str_date.strftime("%d.%m.%Y %H-%M")
        else:
            self.f_mod = ""

        margin = 0

        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(margin, margin, margin, margin)
        v_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v_lay.setSpacing(margin)
        self.setLayout(v_lay)

        self.img_label = QLabel()
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignTop)
        v_lay.addWidget(self.img_label)

        self.name_label = NameLabel()
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignTop)
        v_lay.addWidget(self.name_label)

        self.color_label = ColorLabel()
        self.color_label.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignTop)
        v_lay.addWidget(self.color_label)

        self.setObjectName("thumbnail")
        self.set_no_frame()
        self.setup()

    # 210 пикселей
    def set_pixmap(self, pixmap: QPixmap):
        self.img = pixmap
        pixmap = Utils.pixmap_scale(pixmap, PIXMAP_SIZE[JsonData.pixmap_size_ind])
        self.img_label.setPixmap(pixmap)

    def setup(self):
        if isinstance(self.img, QPixmap):
            pixmap = Utils.pixmap_scale(self.img, PIXMAP_SIZE[JsonData.pixmap_size_ind])
            self.img_label.setPixmap(pixmap)

        row_h = 16

        thumb_w = sum((
            THUMB_W[JsonData.pixmap_size_ind],
            MARGIN.get("w"),
            ))

        thumb_h = sum((
            PIXMAP_SIZE[JsonData.pixmap_size_ind],
            row_h * 2,
            row_h,
            MARGIN.get("h"),
            ))
        
        self.set_text()
        self.adjustSize()

        self.setFixedSize(thumb_w, thumb_h)
        self.img_label.setFixedSize(thumb_w, PIXMAP_SIZE[JsonData.pixmap_size_ind] + 5)
        self.name_label.setFixedSize(thumb_w, row_h * 2)
        self.color_label.setFixedSize(thumb_w, row_h)

        # self.img_label.setStyleSheet("background: gray;")
        # self.name_label.setStyleSheet("background: black;")
        # self.color_label.setStyleSheet("background: light-gray;")

    def set_frame(self):
        self.setStyleSheet(f""" #thumbnail {{ background: {GRAY}; border-radius: 4px; }}""")

    def set_no_frame(self):
        self.setStyleSheet("")

    def add_base_actions(self, context_menu: QMenu):
        view_action = QAction("Просмотр", self)
        view_action.triggered.connect(self.view)
        context_menu.addAction(view_action)

        # Открыть в приложении
        open_menu = QMenu("Открыть в приложении", self)
        context_menu.addMenu(open_menu)

        for name, app_path in IMAGE_APPS.items():
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

        for color, text in COLORS.items():
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

        update_db: bool = self.update_data_db(colors = temp_colors)

        if update_db:
            self.colors = temp_colors
            key = lambda x: list(COLORS.keys()).index(x)
            self.colors = ''.join(sorted(self.colors, key=key))
            self.set_text()

            for item in menu.children():
                item: QAction
                if item.text()[0] in self.colors:
                    item.setChecked(True)

    def get_info(self) -> str:
        rating = "\U00002605" * self.rating
        text = [
            f"Имя: {self.name}",
            f"Тип: {self.type_}",
            f"Путь: {self.src}",
            f"Размер: {self.f_size}" if self.size > 0 else "",
            f"Изменен: {self.f_mod}" if self.f_mod else "",
            f"Рейтинг: {rating}" if rating else "",
            f"Цвета: {self.colors}" if self.colors else ""
            ]
        text = [i for i in text if i]
        return "\n".join(text)

    def set_text(self):
        self.setToolTip(self.get_info())
        self.name_label.set_text(self)
        self.color_label.set_text(self)

    def rating_click(self, menu: QMenu, wid: QAction, rate: int):
        if rate == 1:
            rate = 0

        update_db = self.update_data_db(rating=rate)

        if update_db:
            self.rating = rate
            self.set_text()

            for i in menu.children():
                i: QAction
                i.setChecked(False)
            if rate > 0:
                wid.setChecked(True)

    def set_colors_rating_db(self, colors: str = None, rating: int = None):
        self.colors = colors or self.colors
        self.rating = rating or self.rating
        self.set_text()

    def update_data_db(self, colors: str = None, rating: int = None):
        colors = self.colors if colors is None else colors
        rating = self.rating if rating is None else rating

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
    def __init__(
            self, 
            src: str, 
            size: int = None, 
            mod: int = None, 
            colors: str = None, 
            rating: int = None, 
            pixmap: QPixmap = None, 
            path_to_wid: dict[str, QLabel] = None
            ):
        
        Thumb.__init__(self, src=src, size=size, mod=mod, colors=colors, rating=rating,
                         pixmap=pixmap, path_to_wid=path_to_wid)

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
    def __init__(
        self, 
        src: str, 
        size: int = None, 
        mod: int = None, 
        colors: str = None,
        rating: int = None,
        pixmap: QPixmap = None,
        path_to_wid: dict[str, QLabel] = None
        ):

        Thumb.__init__(self, src=src, size=size, mod=mod, colors=colors, 
                         rating=rating, pixmap=pixmap, path_to_wid=path_to_wid)

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:
        self.clicked.emit()
        
        context_menu = QMenu(parent=self)

        self.add_base_actions(context_menu)

        context_menu.addSeparator()

        show_in_folder = QAction("Показать в папке", self)
        show_in_folder.triggered.connect(lambda: SIGNALS.show_in_folder.emit(self.src))
        context_menu.addAction(show_in_folder)

        context_menu.exec_(self.mapToGlobal(a0.pos()))