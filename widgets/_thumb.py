import subprocess

import sqlalchemy
from PyQt5.QtCore import QMimeData, Qt, QUrl, pyqtSignal
from PyQt5.QtGui import QContextMenuEvent, QDrag, QMouseEvent, QPixmap
from PyQt5.QtWidgets import QApplication, QFrame, QLabel, QMenu, QVBoxLayout
from sqlalchemy.exc import IntegrityError, OperationalError

from cfg import (BLUE, COLORS, FOLDER_SVG, IMG_SVG, MARGIN, PIXMAP_SIZE,
                 STAR_SYM, TEXT_LENGTH, THUMB_W, JsonData)
from database import CACHE, Dbase, OrderItem
from signals import SignalsApp
from utils import URunnable, UThreadPool, Utils

from ._actions import (ColorMenu, CopyPath, FavAdd, FavRemove, Info, OpenInApp,
                       RatingMenu, RevealInFinder, ShowInFolder, View)
from ._base import USvgWidget


class TextLabel(QLabel):
    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignTop)

    def set_text(self, wid: OrderItem) -> list[str]:
        name: str | list = wid.name
        max_row = TEXT_LENGTH[JsonData.pixmap_size_ind]
        lines: list[str] = []

        if len(name) > max_row:

            if wid.rating > 0:
                name = self.short_text(name, max_row)
                lines.append(name)

            else:
                first_line = name[:max_row]
                second_line = name[max_row:]

                if len(second_line) > max_row:
                    second_line = self.short_text(second_line, max_row)

                lines.append(first_line)
                lines.append(second_line)
        else:
            name = lines.append(name)

        if wid.rating > 0:
            lines.append(STAR_SYM * wid.rating)

        self.setText("\n".join(lines))

    def short_text(self, text: str, max_row: int):
        return f"{text[:max_row - 10]}...{text[-7:]}"


class ColorLabel(QLabel):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("font-size: 9px;")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignTop)

    def set_text(self, wid: OrderItem):
        self.setText(wid.colors)


class UpdateThumbData(URunnable):
    def __init__(self, src: str, values: dict, cmd_: callable):

        super().__init__()
        self.cmd_ = cmd_
        self.src = src
        self.values = values

    @URunnable.set_running_state
    def run(self):
        stmt = sqlalchemy.update(CACHE).where(
            CACHE.c.src == self.src
            ).values(
                **self.values
                )
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
    path_to_wid: dict[str, "Thumb"] = {}

    def __init__(self, src: str, size: int, mod: int, colors: str, rating: int):

        QFrame.__init__(self, parent=None)
        OrderItem.__init__(self, src=src, size=size, mod=mod, colors=colors, rating=rating)

        self.img: QPixmap = None
        self.must_hidden: bool = False
        self.row, self.col = 0, 0
        margin = 0

        self.v_lay = QVBoxLayout()
        self.v_lay.setContentsMargins(margin, margin, margin, margin)
        self.v_lay.setSpacing(margin)
        self.setLayout(self.v_lay)

        self.img_wid: USvgWidget | QLabel = USvgWidget()
        self.img_wid.load(IMG_SVG)
        self.v_lay.addWidget(self.img_wid, alignment=Qt.AlignmentFlag.AlignCenter)

        self.name_label = TextLabel()
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
        self.setStyleSheet(f""" #thumbnail {{ background: {BLUE}; border-radius: 4px; }}""")

    def set_no_frame(self):
        self.setStyleSheet("")

    def add_base_actions(self, menu: QMenu):

        view_action = View(parent=menu, src=self.src)
        view_action._clicked.connect(self.open_in_view.emit)
        menu.addAction(view_action)

        open_menu = OpenInApp(parent=menu, src=self.src)
        menu.addMenu(open_menu)

        menu.addSeparator()

        info = Info(parent=menu, src=self.src)
        menu.addAction(info)

        show_in_finder_action = RevealInFinder(parent=menu, src=self.src)
        menu.addAction(show_in_finder_action)

        copy_path = CopyPath(parent=menu, src=self.src)
        menu.addAction(copy_path)

        menu.addSeparator()

        color_menu = ColorMenu(parent=menu, src=self.src, colors=self.colors)
        color_menu._clicked.connect(self.set_color_cmd)
        menu.addMenu(color_menu)

        rating_menu = RatingMenu(parent=menu, src=self.src, rating=self.rating)
        rating_menu._clicked.connect(self.set_rating_cmd)
        menu.addMenu(rating_menu)

    def show_in_finder(self):
        subprocess.call(["open", "-R", self.src])

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

        self.update_thumb_data({"colors": temp_colors}, cmd_)

    def set_rating_cmd(self, rating: int):

        rating = 0 if rating == 1 else rating

        def cmd_():
            self.rating = rating
            self.set_text()

        self.update_thumb_data({"rating": rating}, cmd_)

    def update_thumb_data(self, values: dict, cmd_: callable):
        task_ = UpdateThumbData(self.src, values, cmd_)
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

        if isinstance(self.img_wid, QLabel):
            self.drag.setPixmap(self.img_wid.pixmap())
        else:
            self.drag.setPixmap(QPixmap(FOLDER_SVG))
        
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
    def __init__(self, src: str, size: int, mod: int, colors: str, rating: int):
        super().__init__(src, size, mod, colors, rating)
        
        pixmap_size = PIXMAP_SIZE[JsonData.pixmap_size_ind]
        self.img_wid.load(FOLDER_SVG)
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

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:
        self.select.emit()

        menu = QMenu(parent=self)

        view_action = View(parent=menu, src=self.src)
        view_action._clicked.connect(self.open_in_view.emit)
        menu.addAction(view_action)

        menu.addSeparator()

        info = Info(parent=menu, src=self.src)
        menu.addAction(info)

        show_in_finder_action = RevealInFinder(parent=menu, src=self.src)
        menu.addAction(show_in_finder_action)

        copy_path = CopyPath(parent=menu, src=self.src)
        menu.addAction(copy_path)

        menu.addSeparator()

        if self.src in JsonData.favs:
            cmd_ = lambda: self.fav_cmd(-1)
            self.fav_action = FavRemove(menu, self.src)
            self.fav_action._clicked.connect(cmd_)
            menu.addAction(self.fav_action)

        else:
            cmd_ = lambda: self.fav_cmd(+1)
            self.fav_action = FavAdd(menu, self.src)
            self.fav_action._clicked.connect(cmd_)
            menu.addAction(self.fav_action)

        menu.exec_(self.mapToGlobal(a0.pos()))

 
class ThumbSearch(Thumb):
    def __init__(self, src: str, size: int, mod: int, colors: str, rating: int):
        super().__init__(src, size, mod, colors, rating)

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:
        self.select.emit()
    
        menu_ = QMenu(parent=self)
        self.add_base_actions(menu_)
        menu_.addSeparator()

        cmd_ = lambda: SignalsApp.all.show_in_folder.emit(self.src)
        show_in_folder = ShowInFolder(parent=menu_, src=self.src)
        show_in_folder._clicked.connect(cmd_)
        menu_.addAction(show_in_folder)

        menu_.exec_(self.mapToGlobal(a0.pos()))