import sqlalchemy
from PyQt5.QtCore import QMimeData, Qt, QUrl, pyqtSignal
from PyQt5.QtGui import QContextMenuEvent, QDrag, QMouseEvent, QPixmap
from PyQt5.QtWidgets import QApplication, QFrame, QLabel, QMenu, QVBoxLayout
from sqlalchemy.exc import IntegrityError, OperationalError

from cfg import (BLUE, COLORS, FOLDER_SVG, IMG_SVG, STAR_SYM, Dynamic,
                 JsonData, ThumbData)
from database import CACHE, Dbase, OrderItem
from signals import SignalsApp
from utils import URunnable, UThreadPool, Utils

from ._actions import (ChangeView, ColorMenu, CopyPath, FavAdd, FavRemove,
                       Info, OpenInApp, RatingMenu, RevealInFinder,
                       ShowInFolder, SortMenu, UpdateGrid, View)
from ._base import USvgWidget

COLORS_FONT = "font-size: 9px;"
TEXT_FONT = "font-size: 11px;"
RAD = "border-radius: 4px"


class TextWidget(QLabel):
    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(TEXT_FONT)

    def set_text(self, wid: OrderItem) -> list[str]:
        name: str | list = wid.name
        max_row = ThumbData.MAX_ROW[Dynamic.pixmap_size_ind]
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
        self.setStyleSheet(COLORS_FONT)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

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

    pixmap_size = 0
    thumb_w = 0
    thumb_h = 0
    color_wid_h = 0

    def __init__(self, src: str, size: int, mod: int, colors: str, rating: int):

        QFrame.__init__(self, parent=None)
        OrderItem.__init__(
            self,
            src=src,
            size=size,
            mod=mod,
            colors=colors,
            rating=rating
        )

        self.img: QPixmap = None
        self.must_hidden: bool = False
        self.row, self.col = 0, 0
        margin = 0

        self.v_lay = QVBoxLayout()
        self.v_lay.setContentsMargins(margin, margin, margin, margin)
        self.v_lay.setSpacing(ThumbData.SPACING)
        self.v_lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setLayout(self.v_lay)


        self.img_wid = QFrame()
        self.v_lay.addWidget(self.img_wid, alignment=Qt.AlignmentFlag.AlignCenter)

        self.img_lay = QVBoxLayout()
        self.img_lay.setContentsMargins(0, 0, 0, 0)
        self.img_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_wid.setLayout(self.img_lay)

        self.svg_path = IMG_SVG
        svg_wid = USvgWidget(src=self.svg_path, size=self.pixmap_size)
        self.img_lay.addWidget(svg_wid)

        self.text_wid = TextWidget()
        self.v_lay.addWidget(self.text_wid, alignment=Qt.AlignmentFlag.AlignCenter)

        self.color_wid = ColorLabel()
        self.v_lay.addWidget(self.color_wid, alignment=Qt.AlignmentFlag.AlignCenter)

        for i in (self.img_wid, self.text_wid, self.color_wid):
            i.mouseReleaseEvent = self.mouse_release
            i.mousePressEvent = self.mouse_press
            i.mouseMoveEvent = self.mouse_move
            i.mouseDoubleClickEvent = self.mouse_d_click
            i.contextMenuEvent = self.mouse_r_click

        self.setup()
        self.set_no_frame()

    @classmethod
    def calculate_size(cls):
        ind = Dynamic.pixmap_size_ind
        cls.pixmap_size = ThumbData.PIXMAP_SIZE[ind]
        cls.thumb_w = ThumbData.THUMB_W[ind]
        cls.thumb_h = ThumbData.THUMB_H[ind]
        cls.color_wid_h = ThumbData.COLOR_WID_H

    def set_pixmap(self, pixmap: QPixmap):
        svg = self.img_wid.findChild(USvgWidget)

        try:
            svg.deleteLater()
        except RuntimeError:
            return

        img_wid = QLabel()
        img_wid.setPixmap(Utils.pixmap_scale(pixmap, self.pixmap_size))
        self.img_lay.addWidget(img_wid, alignment=Qt.AlignmentFlag.AlignCenter)

        self.img = pixmap

    def setup(self):

        #  при первой инициации нужно установить текст в виджеты
        for i in (self.text_wid, self.color_wid):
            i.set_text(self)

        self.setFixedSize(
            self.thumb_w,
            self.thumb_h
        )

        # фиксированная высота строки цветовых меток чтобы они не обрезались
        self.color_wid.setFixedHeight(
            self.color_wid_h
        )

        # рамка вокруг pixmap при выделении Thumb
        self.img_wid.setFixedSize(
            self.pixmap_size + ThumbData.OFFSET,
            self.pixmap_size + ThumbData.OFFSET
        )

        img_lbl = self.img_wid.findChild(QLabel)

        if isinstance(img_lbl, QLabel):
            img_lbl.setPixmap(
                Utils.pixmap_scale(
                    pixmap=self.img,
                    size=self.pixmap_size
                )
            )

    def set_frame(self):
        self.text_wid.setStyleSheet(
            f"""
                background: {BLUE};
                {TEXT_FONT};
                {RAD};
                padding: 2px;
            """
        )
        self.img_wid.setStyleSheet(
            f"""
                background: {BLUE};
                {TEXT_FONT};
                {RAD};
                padding: 2px;
            """
        )

    def set_no_frame(self):
        for i in (self.text_wid, self.img_wid):
            style = i.styleSheet().replace(BLUE, "transparent")
            i.setStyleSheet(style)

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

        menu.addSeparator()

        change_view = ChangeView(menu, self.src)
        menu.addMenu(change_view)

        sort_menu = SortMenu(parent=menu)
        menu.addMenu(sort_menu)

    def set_color_cmd(self, color: str):

        if color not in self.colors:
            temp_colors = self.colors + color
        else:
            temp_colors = self.colors.replace(color, "")

        def cmd_():
            self.colors = temp_colors
            key = lambda x: list(COLORS.keys()).index(x)
            self.colors = ''.join(sorted(self.colors, key=key))

            # сбрасываем фиксированную ширину для изменения текста
            self.color_wid.setMinimumWidth(0)
            self.color_wid.setMaximumWidth(50)
            self.color_wid.set_text(self)

            self.text_changed.emit()

            # заново собираем размеры виджета с учетом новых цветовых меток
            self.setup()

        self.update_thumb_data(
            values={"colors": temp_colors},
            cmd_=cmd_
        )

    def set_rating_cmd(self, rating: int):

        rating = 0 if rating == 1 else rating

        def cmd_():
            self.rating = rating
            self.text_wid.set_text(self)
            self.text_changed.emit()

        self.update_thumb_data(
            values={"rating": rating},
            cmd_=cmd_
        )

    def update_thumb_data(self, values: dict, cmd_: callable):
        task_ = UpdateThumbData(self.src, values, cmd_)
        UThreadPool.start(task_)

    def mouse_release(self, a0: QMouseEvent | None) -> None:
        self.select.emit()

    def mouse_press(self, a0: QMouseEvent | None) -> None:
        if a0.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = a0.pos()

    def mouse_move(self, a0: QMouseEvent | None) -> None:
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

        img_wid = self.img_wid.findChild(QLabel)

        if isinstance(img_wid, QLabel):
            self.drag.setPixmap(img_wid.pixmap())
        else:
            self.drag.setPixmap(QPixmap(self.svg_path))
        
        url = [QUrl.fromLocalFile(self.src)]
        self.mime_data.setUrls(url)

        self.drag.setMimeData(self.mime_data)
        self.drag.exec_(Qt.DropAction.CopyAction)

    def mouse_d_click(self, a0: QMouseEvent | None) -> None:
        self.open_in_view.emit()

    def mouse_r_click(self, a0: QContextMenuEvent | None) -> None:
        self.select.emit()
        context_menu = QMenu(self)
        self.add_base_actions(context_menu)
        context_menu.exec_(self.mapToGlobal(a0.pos()))


class ThumbFolder(Thumb):
    def __init__(self, src: str, size: int, mod: int, colors: str, rating: int):
        super().__init__(src, size, mod, colors, rating)

        self.svg_path = FOLDER_SVG
        img_wid = self.img_wid.findChild(USvgWidget)
        img_wid.load(self.svg_path)

    def fav_cmd(self, offset: int):
        self.fav_action.triggered.disconnect()
        if 0 + offset == 1:
            SignalsApp.all_.fav_cmd.emit({"cmd": "add", "src": self.src})
            self.fav_action.setText("Удалить из избранного")
            self.fav_action.triggered.connect(lambda: self.fav_cmd(-1))
        else:
            SignalsApp.all_.fav_cmd.emit({"cmd": "del", "src": self.src})
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

        menu.addSeparator()

        update_ = UpdateGrid(parent=menu, src=JsonData.root)
        menu.addAction(update_)

        change_view = ChangeView(menu, self.src)
        menu.addMenu(change_view)
        
        sort_menu = SortMenu(parent=menu)
        menu.addMenu(sort_menu)


        menu.exec_(self.mapToGlobal(a0.pos()))

 
class ThumbSearch(Thumb):
    def __init__(self, src: str, size: int, mod: int, colors: str, rating: int):
        super().__init__(src, size, mod, colors, rating)

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:
        self.select.emit()
    
        menu_ = QMenu(parent=self)
        self.add_base_actions(menu_)
        menu_.addSeparator()

        cmd_ = lambda: SignalsApp.all_.show_in_folder.emit(self.src)
        show_in_folder = ShowInFolder(parent=menu_, src=self.src)
        show_in_folder._clicked.connect(cmd_)
        menu_.addAction(show_in_folder)

        menu_.exec_(self.mapToGlobal(a0.pos()))