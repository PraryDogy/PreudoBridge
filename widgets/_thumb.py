import datetime
import os
import subprocess

import sqlalchemy
from PyQt5.QtCore import QMimeData, QObject, Qt, QUrl, pyqtSignal
from PyQt5.QtGui import QContextMenuEvent, QDrag, QMouseEvent, QPixmap
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import (QAction, QApplication, QFrame, QLabel, QMenu,
                             QVBoxLayout)
from sqlalchemy.exc import IntegrityError, OperationalError

from cfg import (COLORS, FOLDER, GRAY, IMAGE_APPS, MARGIN, PIXMAP_SIZE,
                 STAR_SYM, TEXT_LENGTH, THUMB_W, JsonData)
from database import CACHE, Dbase, OrderItem
from signals import SignalsApp
from utils import URunnable, UThreadPool, Utils

from .win_info import WinInfo

IMAGES = "images"
IMG_ICON = os.path.join(IMAGES, "img.svg")
FOLDER_ICON = os.path.join(IMAGES, "folder.svg")


class NameLabel(QLabel):
    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignTop)

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
            name.append(STAR_SYM * wid.rating)

        self.setText("\n".join(name))


class ColorLabel(QLabel):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("font-size: 9px;")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignTop)

    def set_text(self, wid: OrderItem):
        self.setText(wid.colors)


class UpdateThumbData(URunnable):
    def __init__(self, src: str, value_name: str, value: int | str, cmd_: callable):
        """value_name: colors, rating"""
        super().__init__()

        self.cmd_ = cmd_
        self.src = src
        self.value_name = value_name
        self.value = value

    def run(self):
        values_ = {self.value_name: self.value}
        stmt = sqlalchemy.update(CACHE).where(CACHE.c.src == self.src).values(**values_)
        conn = Dbase.engine.connect()

        try:
            conn.execute(stmt)
            conn.commit()
            self.finalize()
        except (OperationalError, IntegrityError) as e:
            conn.rollback()
            Utils.print_error(self, e)

        conn.close()

    def finalize(self):
        self.cmd_()


class Thumb(OrderItem, QFrame):
    select = pyqtSignal()
    open_in_view = pyqtSignal()
    text_changed = pyqtSignal()

    def __init__(
            self,
            src: str,
            size: int = None,
            mod: int = None,
            colors: str = None,
            rating: int = None,
            pixmap: QPixmap = None,
            ):

        QFrame.__init__(self, parent=None)
        OrderItem.__init__(self, src=src, size=size, mod=mod, colors=colors, rating=rating)

        self.img: QPixmap = pixmap
        self.must_hidden: bool = False
        self.row, self.col = 0, 0

        margin = 0
        pixmap_size = PIXMAP_SIZE[JsonData.pixmap_size_ind]

        self.v_lay = QVBoxLayout()
        self.v_lay.setContentsMargins(margin, margin, margin, margin)
        self.v_lay.setSpacing(margin)
        self.setLayout(self.v_lay)

        self.img_wid: QSvgWidget | QLabel = QSvgWidget()
        self.img_wid.load(IMG_ICON)
        self.img_wid.renderer().setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self.v_lay.addWidget(self.img_wid, alignment=Qt.AlignmentFlag.AlignCenter)

        self.name_label = NameLabel()
        self.v_lay.addWidget(self.name_label)

        self.color_label = ColorLabel()
        self.v_lay.addWidget(self.color_label)

        self.setObjectName("thumbnail")
        self.set_no_frame()
        self.setup()

    # 210 пикселей
    def set_pixmap(self, pixmap: QPixmap):
        flag_ = Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignTop
        pixmap_size = PIXMAP_SIZE[JsonData.pixmap_size_ind]

        self.img_wid.deleteLater()
        self.img_wid = QLabel()
        self.img_wid.setAlignment(flag_)
        self.v_lay.insertWidget(0, self.img_wid)

        self.img = pixmap
        self.img_wid.setPixmap(Utils.pixmap_scale(pixmap, pixmap_size))

    def setup(self):
        pixmap_size = PIXMAP_SIZE[JsonData.pixmap_size_ind]
        row_h = 16

        thumb_w = sum((
            THUMB_W[JsonData.pixmap_size_ind],
            MARGIN.get("w"),
            ))

        thumb_h = sum((
            pixmap_size,
            row_h * 2,
            row_h,
            MARGIN.get("h"),
            ))
        
        self.set_text()
        self.adjustSize()

        self.setFixedSize(thumb_w, thumb_h)
        self.name_label.setFixedSize(thumb_w, row_h * 2)
        self.color_label.setFixedSize(thumb_w, row_h)

        if isinstance(self.img_wid, QLabel):
            self.img_wid.setPixmap( Utils.pixmap_scale(self.img, pixmap_size))
        else:
            self.img_wid.setFixedSize(pixmap_size, pixmap_size)

    def set_frame(self):
        self.setStyleSheet(f""" #thumbnail {{ background: {GRAY}; border-radius: 4px; }}""")

    def set_no_frame(self):
        self.setStyleSheet("")

    def add_base_actions(self, context_menu: QMenu):
        view_action = QAction("Просмотр", self)
        view_action.triggered.connect(self.open_in_view.emit)
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

            cmd_ = lambda e, c=color: self.set_color_cmd(c)
            wid.triggered.connect(cmd_)
            color_menu.addAction(wid)

        rating_menu = QMenu("Рейтинг", self)
        context_menu.addMenu(rating_menu)

        for rating in range(1, 6):
            wid = QAction(parent=rating_menu, text=STAR_SYM * rating)
            wid.setCheckable(True)

            if self.rating == rating:
                wid.setChecked(True)

            cmd_ = lambda e, r=rating: self.set_rating_cmd(r)
            wid.triggered.connect(cmd_)
            rating_menu.addAction(wid)

    def show_info_win(self):
        self.win_info = WinInfo(self.get_info())
        Utils.center_win(parent=Utils.get_main_win(), child=self.win_info)
        self.win_info.show()

    def open_in_app(self, app_path: str):
        subprocess.call(["open", "-a", app_path, self.src])

    def show_in_finder(self):
        subprocess.call(["open", "-R", self.src])

    def get_info(self) -> str:
        rating = STAR_SYM * self.rating

        if self.type_ == FOLDER:
            self.size = Utils.get_folder_size_applescript(self.src)
            
        size_ = round(self.size / (1024**2), 2)

        if size_ < 1000:
            f_size = f"{size_} МБ"
        else:
            size_ = round(self.size / (1024**3), 2)
            f_size = f"{size_} ГБ"

        if self.mod:
            str_date = datetime.datetime.fromtimestamp(self.mod).replace(microsecond=0)
            f_mod: str = str_date.strftime("%d.%m.%Y %H:%M")
        else:
            self.f_mod = ""

        text = [
            f"Имя*** {self.name}",
            f"Тип*** {self.type_}",
            f"Путь*** {self.src}",
            f"Размер*** {f_size}" if self.size > 0 else "",
            f"Изменен*** {f_mod}" if f_mod else "",
            f"Рейтинг*** {rating}" if rating else "",
            f"Цвета*** {self.colors}" if self.colors else ""
            ]
        text = [i for i in text if i]
        return "\n".join(text)

    def set_text(self):
        self.name_label.set_text(self)
        self.color_label.set_text(self)
        self.text_changed.emit()

    def set_color_cmd(self, color: str):

        if color not in self.colors:
            temp_colors = self.colors + color
        else:
            temp_colors = self.colors.replace(color, "")

        def cmd_():
            self.colors = temp_colors
            key = lambda x: list(COLORS.keys()).index(x)
            self.colors = ''.join(sorted(self.colors, key=key))
            self.set_text()

        self.update_thumb_data("colors", temp_colors, cmd_)

    def set_rating_cmd(self, rating: int):

        rating = 0 if rating == 1 else rating

        def cmd_():
            self.rating = rating
            self.set_text()

        self.update_thumb_data("rating", rating, cmd_)

    def update_thumb_data(self, value_name: str, value: str | int, cmd_: callable):
        task_ = UpdateThumbData(self.src, value_name, value, cmd_)
        UThreadPool.pool.start(task_)

    def mouseReleaseEvent(self, a0: QMouseEvent | None) -> None:
        self.select.emit()

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

        self.select.emit()

        self.drag = QDrag(self)
        self.mime_data = QMimeData()
        self.drag.setPixmap(self.img_wid.pixmap())
        
        url = [QUrl.fromLocalFile(self.src)]
        self.mime_data.setUrls(url)

        self.drag.setMimeData(self.mime_data)
        self.drag.exec_(Qt.DropAction.CopyAction)

    def mouseDoubleClickEvent(self, a0: QMouseEvent | None) -> None:
        self.open_in_view.emit()

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:
        self.select.emit()
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
            ):
        
        Thumb.__init__(
            self,
            src=src,
            size=size,
            mod=mod,
            colors=colors,
            rating=rating, pixmap=pixmap
            )
        
        pixmap_size = PIXMAP_SIZE[JsonData.pixmap_size_ind]
        self.img_wid.load(FOLDER_ICON)
        self.img_wid.setFixedSize(pixmap_size, pixmap_size)

    def fav_cmd(self, offset: int):
        self.fav_action.triggered.disconnect()
        if 0 + offset == 1:
            SignalsApp.all.fav_cmd.emit("add", self.src)
            self.fav_action.setText("Удалить из избранного")
            self.fav_action.triggered.connect(lambda: self.fav_cmd(-1))
        else:
            SignalsApp.all.fav_cmd.emit("del", self.src)
            self.fav_action.setText("Добавить в избранное")
            self.fav_action.triggered.connect(lambda: self.fav_cmd(+1))

    def show_info_win(self):
        self.win_info = WinInfo(self.get_info())
        Utils.center_win(parent=Utils.get_main_win(), child=self.win_info)
        self.win_info.show()

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:
        self.select.emit()

        context_menu = QMenu(parent=self)

        view_action = QAction("Открыть", self)
        view_action.triggered.connect(self.open_in_view.emit)
        context_menu.addAction(view_action)

        context_menu.addSeparator()

        info = QAction("Инфо", self)
        info.triggered.connect(self.show_info_win)
        context_menu.addAction(info)

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
        ):

        Thumb.__init__(
            self,
            src=src, 
            size=size, 
            mod=mod, 
            colors=colors,
            rating=rating, 
            pixmap=pixmap
            )

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:
        self.select.emit()
        
        context_menu = QMenu(parent=self)

        self.add_base_actions(context_menu)

        context_menu.addSeparator()

        show_in_folder = QAction("Показать в папке", self)
        show_in_folder.triggered.connect(lambda: SignalsApp.all.show_in_folder.emit(self.src))
        context_menu.addAction(show_in_folder)

        context_menu.exec_(self.mapToGlobal(a0.pos()))