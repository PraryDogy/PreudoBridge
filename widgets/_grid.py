import os
import shutil

import sqlalchemy
from PyQt5.QtCore import QMimeData, QObject, Qt, QTimer, QUrl, pyqtSignal
from PyQt5.QtGui import (QContextMenuEvent, QDrag, QKeyEvent, QMouseEvent,
                         QPixmap)
from PyQt5.QtWidgets import (QApplication, QFrame, QGridLayout, QLabel, QMenu,
                             QScrollArea, QVBoxLayout, QWidget)
from sqlalchemy.exc import IntegrityError, OperationalError

from cfg import Dynamic, JsonData, Static, ThumbData
from database import CACHE, ColumnNames, Dbase, OrderItem
from signals import SignalsApp
from utils import URunnable, UThreadPool, Utils

from ._actions import (ChangeView, ColorMenu, CopyPath, CreateFolder,
                       DeleteFinderItem, FavAdd, FavRemove, FindHere, Info,
                       OpenInApp, RatingMenu, RevealInFinder, ShowInFolder,
                       SortMenu, UpdateGrid, View)
from ._base import BaseMethods, OpenWin, USvgWidget
from .list_file_system import ListFileSystem
from .win_find_here import WinFindHere
from .win_sys import WinCopy

SELECTED = "selected"
COLORS_FONT = "font-size: 9px;"
TEXT_FONT = "font-size: 11px;"
RAD = "border-radius: 4px"
IMG_WID_ATTR = "img_wid"


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
        try:
            self.cmd_()
        except RuntimeError as e:
            Utils.print_error(parent=None, error=e)


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
            lines.append(Static.STAR_SYM * wid.rating)

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


class Thumb(OrderItem, QFrame):
    select = pyqtSignal()
    open_in_view = pyqtSignal()
    text_changed = pyqtSignal()
    find_here = pyqtSignal()

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


        self.img_frame = QFrame()
        self.v_lay.addWidget(self.img_frame, alignment=Qt.AlignmentFlag.AlignCenter)

        self.img_frame_lay = QVBoxLayout()
        self.img_frame_lay.setContentsMargins(0, 0, 0, 0)
        self.img_frame_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_frame.setLayout(self.img_frame_lay)

        self.svg_path = Static.IMG_SVG
        self.svg_wid = USvgWidget(src=self.svg_path, size=self.pixmap_size)
        self.img_frame_lay.addWidget(self.svg_wid)

        self.text_wid = TextWidget()
        self.v_lay.addWidget(self.text_wid, alignment=Qt.AlignmentFlag.AlignCenter)

        self.color_wid = ColorLabel()
        self.v_lay.addWidget(self.color_wid, alignment=Qt.AlignmentFlag.AlignCenter)

        for i in (self.img_frame, self.text_wid, self.color_wid):
            i.mouseReleaseEvent = self.mouse_release
            i.mousePressEvent = self.mouse_press
            i.mouseMoveEvent = self.mouse_move
            i.mouseDoubleClickEvent = self.mouse_d_click
            i.contextMenuEvent = self.mouse_r_click

        self.setup()
        self.set_no_frame()

        # self.setStyleSheet("background: gray;")

    @classmethod
    def calculate_size(cls):
        ind = Dynamic.pixmap_size_ind
        cls.pixmap_size = ThumbData.PIXMAP_SIZE[ind]
        cls.thumb_w = ThumbData.THUMB_W[ind]
        cls.thumb_h = ThumbData.THUMB_H[ind]
        cls.color_wid_h = ThumbData.COLOR_WID_H

    def set_pixmap(self, pixmap: QPixmap):
        self.svg_wid.deleteLater()

        self.img_wid = QLabel()
        self.img_wid.setPixmap(Utils.pixmap_scale(pixmap, self.pixmap_size))
        self.img_frame_lay.addWidget(self.img_wid, alignment=Qt.AlignmentFlag.AlignCenter)

        self.img = pixmap

    def setup(self):

        # при первой инициации нужно установить текст в виджеты
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
        self.img_frame.setFixedSize(
            self.pixmap_size + ThumbData.OFFSET,
            self.pixmap_size + ThumbData.OFFSET
        )

        if hasattr(self, IMG_WID_ATTR):
            self.img_wid.setPixmap(
                Utils.pixmap_scale(
                    pixmap=self.img,
                    size=self.pixmap_size
                )
            )
        else:
            self.svg_wid.setFixedSize(self.pixmap_size, self.pixmap_size)

    def set_frame(self):

        self.text_wid.setStyleSheet(
            f"""
                background: {Static.BLUE};
                {TEXT_FONT};
                {RAD};
                padding: 2px;
            """
        )

        self.img_frame.setStyleSheet(
            f"""
                background: {Static.GRAY_UP_BTN};
                {TEXT_FONT};
                {RAD};
            """
        )

    def set_no_frame(self):
    
        self.text_wid.setStyleSheet(
            f"""
                background: transparent;
                {TEXT_FONT};
                {RAD};
                padding: 2px;
            """
        )
    
        self.img_frame.setStyleSheet(
            f"""
                background: transparent;
                {TEXT_FONT};
                {RAD};
            """
        )

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

        menu.addSeparator()

        upd_ = UpdateGrid(menu, JsonData.root)
        menu.addAction(upd_)

        find_here = FindHere(parent=menu)
        find_here.clicked_.connect(self.find_here.emit)
        menu.addAction(find_here)

        delete_item = DeleteFinderItem(menu=menu, path=self.src)
        menu.addAction(delete_item)

    def set_color_cmd(self, color: str):

        if color not in self.colors:
            temp_colors = self.colors + color
        else:
            temp_colors = self.colors.replace(color, "")

        def cmd_():
            self.colors = temp_colors
            key = lambda x: list(Static.COLORS.keys()).index(x)
            self.colors = ''.join(sorted(self.colors, key=key))

            # сбрасываем фиксированную ширину для изменения текста
            self.color_wid.setMinimumWidth(0)
            self.color_wid.setMaximumWidth(50)
            self.color_wid.set_text(self)

            self.text_changed.emit()

            # заново собираем размеры виджета с учетом новых цветовых меток
            self.setup()

        self.update_thumb_data(
            values={ColumnNames.COLORS: temp_colors},
            cmd_=cmd_
        )

    def set_rating_cmd(self, rating: int):

        rating = 0 if rating == 1 else rating

        def cmd_():
            self.rating = rating
            self.text_wid.set_text(self)
            self.text_changed.emit()

        self.update_thumb_data(
            values={ColumnNames.RATING: rating},
            cmd_=cmd_
        )

    def update_thumb_data(self, values: dict, cmd_: callable):
        self.task_ = UpdateThumbData(self.src, values, cmd_)
        UThreadPool.start(self.task_)

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

        if hasattr(self, IMG_WID_ATTR):
            self.drag.setPixmap(self.img_wid.pixmap())
        else:
            self.drag.setPixmap(QPixmap(self.svg_path))
        
        urls = [QUrl.fromLocalFile(self.src)]
        self.mime_data.setText(self.src)        

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

        self.svg_path = Static.FOLDER_SVG
        img_wid = self.img_frame.findChild(USvgWidget)
        img_wid.load(self.svg_path)

        for i in (self.img_frame, self.text_wid, self.color_wid):
            i.contextMenuEvent = self.mouse_r_click

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

    def mouse_r_click(self, a0: QContextMenuEvent | None) -> None:
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

        change_view = ChangeView(menu, self.src)
        menu.addMenu(change_view)
        
        sort_menu = SortMenu(parent=menu)
        menu.addMenu(sort_menu)

        menu.addSeparator()

        update_ = UpdateGrid(parent=menu, src=JsonData.root)
        menu.addAction(update_)

        find_here = FindHere(parent=menu)
        find_here.clicked_.connect(self.find_here.emit)
        menu.addAction(find_here)

        delete_item = DeleteFinderItem(menu=menu, path=self.src)
        menu.addAction(delete_item)

        menu.exec_(self.mapToGlobal(a0.pos()))

 
class ThumbSearch(Thumb):
    def __init__(self, src: str, size: int, mod: int, colors: str, rating: int):
        super().__init__(src, size, mod, colors, rating)

        for i in (self.img_frame, self.text_wid, self.color_wid):
            i.contextMenuEvent = self.mouse_r_click

    def show_in_folder_cmd(self):
        root = os.path.dirname(self.src)
        SignalsApp.all_.load_standart_grid.emit(root)
        SignalsApp.all_.move_to_wid_delayed.emit(self.src)

    def mouse_r_click(self, a0: QContextMenuEvent | None) -> None:
        self.select.emit()
    
        menu_ = QMenu(parent=self)
        self.add_base_actions(menu_)
        menu_.addSeparator()

        show_in_folder = ShowInFolder(parent=menu_, src=self.src)
        show_in_folder._clicked.connect(self.show_in_folder_cmd)
        menu_.addAction(show_in_folder)

        menu_.exec_(self.mapToGlobal(a0.pos()))


class WorkerSignals(QObject):
    finished_ = pyqtSignal()


class FileCopyThread(URunnable):

    def __init__(self, src: str, dest: str):
        super().__init__()
        self.signals_ = WorkerSignals()

        self.src = os.sep + src.strip(os.sep)
        self.dest = os.sep + dest.strip(os.sep)

    @URunnable.set_running_state
    def run(self):

        try:
            self.main()
        except (RuntimeError, Exception) as e:
            print("grid error copy file / folder", e)

        self.signals_.finished_.emit()

    def main(self):

        if os.path.isfile(self.src):
            new_src: str = shutil.copy(self.src, self.dest)
            new_src = os.sep + new_src.strip(os.sep)

            self.migrate_data(
                old_src = self.src,
                new_src = new_src
            )


    # этот метод пойдет в отдельный класс, т.к. будет нужен для реализации
    # копировать вставить хоткеями
    def migrate_data(self, old_src: str, new_src: str):
        wid = Thumb.path_to_wid.get(self.src)
        if wid and (wid.colors or wid.rating):

            conn = Dbase.engine.connect()

            # если приложение уже успело создать запись в БД о новом объекте
            # удалим эту запись, т.к. стандартно запись в БД происходит
            # с пустыми значениями COLORS и RATING
            q = sqlalchemy.select(CACHE).where(CACHE.c.src == new_src)
            new_data = conn.execute(q).first()

            if new_data:

                q = sqlalchemy.delete(CACHE).where(CACHE.c.src == new_src)

                try:
                    conn.execute(q)
                    conn.commit()

                except (IntegrityError, OperationalError) as e:
                    conn.rollback()
                    print("grid.py > FileCopyThread > delete from DB", e)


            # если в БД есть данные об исходном объекте, создаем
            # данные на их основе для нового объекта
            q = sqlalchemy.select(CACHE).where(CACHE.c.src == self.src)
            old_data = conn.execute(q).mappings().first()

            if old_data:

                old_hash_path = old_data.get(ColumnNames.HASH_PATH)
                new_hash_path = Utils.create_hash_path(new_src)
                
                shutil.copy(old_hash_path, new_hash_path)

                new_values = {
                    ColumnNames.SRC: new_src,
                    ColumnNames.HASH_PATH: new_hash_path,
                    ColumnNames.ROOT: os.path.dirname(new_src),
                    ColumnNames.CATALOG: "",
                    ColumnNames.NAME: os.path.basename(new_src),
                    ColumnNames.TYPE: os.path.splitext(new_src)[1],
                    ColumnNames.SIZE: old_data.get(ColumnNames.SIZE),

                    # мы берем новую дату изменения
                    # т.к. она меняется после копирования
                    ColumnNames.MOD: os.stat(new_src).st_mtime,

                    ColumnNames.RESOL: old_data.get(ColumnNames.RESOL),
                    ColumnNames.COLORS: old_data.get(ColumnNames.COLORS),
                    ColumnNames.RATING: old_data.get(ColumnNames.RATING)
                }

                q = sqlalchemy.insert(CACHE).values(new_values)

                try:
                    conn.execute(q)
                    conn.commit()
                except (IntegrityError, OperationalError) as e:
                    print("grid.py > FileCopyThread > insert to DB", e)
                    conn.rollback()

            conn.close()


class Grid(BaseMethods, QScrollArea):
    rearranged = pyqtSignal()

    def __init__(self, width: int):
        Thumb.path_to_wid.clear()

        QScrollArea.__init__(self)
        BaseMethods.__init__(self)

        self.setAcceptDrops(True)
        self.setWidgetResizable(True)

        self.curr_cell: tuple = (0, 0)
        self.cell_to_wid: dict[tuple, Thumb] = {}
        self.ordered_widgets: list[OrderItem | Thumb | ThumbFolder | ThumbSearch] = []
        self.ww = width

        # Посколько сетка может множество раз перезагружаться
        # прежде нужно отключить прошлые подключения чтобы не было
        # дублирования подклювчений
        SignalsApp.disconnect_grid()

        SignalsApp.all_.resize_grid.connect(self.resize_)
        SignalsApp.all_.sort_grid.connect(self.order_)
        SignalsApp.all_.filter_grid.connect(self.filter_)
        SignalsApp.all_.move_to_wid.connect(self.select_new_widget)

        self.main_wid = QWidget()

        flags = Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(Static.GRID_SPACING)
        self.grid_layout.setAlignment(flags)

        self.main_wid.setLayout(self.grid_layout)

    def set_main_wid(self):
        self.setWidget(self.main_wid)

    def select_new_widget(self, data: tuple | str | Thumb):
        if isinstance(data, Thumb):
            coords = data.row, data.col
            new_wid = data

        elif isinstance(data, tuple):
            coords = data
            new_wid = self.cell_to_wid.get(data)

        elif isinstance(data, str):
            # мы пытаемся найти виджет по пути к изображению
            # но сетка может обновиться уже без виджета с таким путем

            new_wid = Thumb.path_to_wid.get(data)

            if new_wid:
                coords = new_wid.row, new_wid.col

            else:
                return

        prev_wid = self.cell_to_wid.get(self.curr_cell)

        if isinstance(new_wid, Thumb):
            prev_wid.set_no_frame()
            new_wid.set_frame()
            self.curr_cell = coords
            self.ensureWidgetVisible(new_wid)

            # задаем этот аттрибут чтобы при rearrange сетки выделенный виджет
            # мог выделиться снова
            setattr(self, SELECTED, True)

            cmd_ = lambda: SignalsApp.all_.bar_bottom_cmd.emit(
                {"src" : new_wid.src}
            )
            QTimer.singleShot(100, cmd_)
        else:
            try:
                prev_wid.set_frame()
            except AttributeError:
                pass

        self.setFocus()

    def reset_selection(self):

        widget = self.cell_to_wid.get(self.curr_cell)

        if isinstance(widget, QFrame):
            widget.set_no_frame()
            self.curr_cell: tuple = (0, 0)
    
    def set_rating(self, rating: int):
        rating_data = {48: 0, 49: 1, 50: 2, 51: 3, 52: 4, 53: 5}
        wid: Thumb = self.cell_to_wid.get(self.curr_cell)

        if isinstance(wid, Thumb):
            wid.set_rating_cmd(rating_data.get(rating))
            self.select_new_widget(self.curr_cell)

    def order_(self):
        self.ordered_widgets = OrderItem.order_items(self.ordered_widgets)
        
        Thumb.all = {
            wid.src: wid
            for wid in self.ordered_widgets
            if isinstance(wid, Thumb)
            }
        
        self.rearrange()

    def filter_(self):
        for wid in self.ordered_widgets:
            show_widget = True

            if Dynamic.rating_filter > 0:
                if not (Dynamic.rating_filter >= wid.rating > 0):
                    show_widget = False

            if Dynamic.color_filters:
                if not any(color for color in wid.colors if color in Dynamic.color_filters):
                    show_widget = False

            if show_widget:
                wid.must_hidden = False
                wid.show()
            else:
                wid.must_hidden = True
                wid.hide()

        self.rearrange()

    def resize_(self):
        Thumb.calculate_size()
        for wid in self.ordered_widgets:
            wid.setup()
        self.rearrange()

    def reselect(func: callable):
        
        def wrapper(self, *args, **kwargs):

            # если Thumb не был выделен пользователем вручную
            # то повторного выделения при rearrange не будет
            if hasattr(self, SELECTED):

                assert isinstance(self, Grid)
                widget = self.cell_to_wid.get(self.curr_cell)

                if isinstance(widget, QFrame):
                    src = widget.src
                else:
                    src = None

            func(self, *args, **kwargs)

            if hasattr(self, SELECTED):
                self.select_new_widget(src)

        return wrapper

    @reselect
    def rearrange(self, width: int = None):
        # этот метод отвечает за перетасовку
        # виджетов, поэтому отсюда мы отсылаем в инициатор self.ww
        # перетасовка происходит при любом изменении виджета

        if width:
            self.ww = width
            col_count = Utils.get_clmn_count(width)
        else:
            col_count = Utils.get_clmn_count(self.ww)

        self.reset_selection()
        self.cell_to_wid.clear()

        row, col = 0, 0

        for wid in self.ordered_widgets:

            if wid.must_hidden:
                continue

            self.grid_layout.addWidget(wid, row, col)
            self.cell_to_wid[row, col] = wid
            wid.row, wid.col = row, col

            col += 1
            if col >= col_count:
                col = 0
                row += 1

        Thumb.path_to_wid = {
            wid.src: wid
            for coords, wid in self.cell_to_wid.items()
        }

        self.rearranged.emit()

    def add_widget_data(self, wid: Thumb, row: int, col: int):
        wid.row, wid.col = row, col
        self.cell_to_wid[row, col] = wid
        Thumb.path_to_wid[wid.src] = wid
        self.ordered_widgets.append(wid)

    def open_in_view(self, wid: Thumb):

        if wid is None:
            return

        elif wid.type_ == Static.FOLDER_TYPE:
            SignalsApp.all_.new_history_item.emit(wid.src)
            SignalsApp.all_.load_standart_grid.emit(wid.src)

        else:
            OpenWin.view(Utils.get_main_win(), wid.src)

    def select_after_list(self):
        wid = Thumb.path_to_wid.get(ListFileSystem.last_selection)

        if isinstance(wid, Thumb):
            self.select_new_widget(wid)
            self.ensureWidgetVisible(wid)
            ListFileSystem.last_selection = None

    def fav_cmd(self, offset: int):
        self.fav_action.triggered.disconnect()
        if 0 + offset == 1:

            SignalsApp.all_.fav_cmd.emit({"cmd": "add", "src": JsonData.root})
            self.fav_action.setText("Удалить из избранного")
            self.fav_action.triggered.connect(lambda: self.fav_cmd(-1))

        else:
            SignalsApp.all_.fav_cmd.emit({"cmd": "del", "src": JsonData.root})
            self.fav_action.setText("Добавить в избранное")
            self.fav_action.triggered.connect(lambda: self.fav_cmd(+1))

    def remove_selection(self):
        """
        удаляет только стилистическое выделение
        но не сбрасывает curr_cell
        """
        wid = self.cell_to_wid.get(self.curr_cell)

        if isinstance(wid, Thumb):
            wid.set_no_frame()

        # клик по пустоте снимает выделение с виджета
        # и чтобы виджет не выделялся при rearrange
        if hasattr(self, SELECTED):
            delattr(self, SELECTED)

        self.setFocus()

        cmd_ = lambda: SignalsApp.all_.bar_bottom_cmd.emit({"src": JsonData.root})
        QTimer.singleShot(100, cmd_)

    def open_find_here_win(self, *args):
        self.find_here_win = WinFindHere()
        self.find_here_win.finished_.connect(self.find_here_cmd)
        Utils.center_win(parent=self.window(), child=self.find_here_win)
        self.find_here_win.show()

    def find_here_cmd(self, text: str):
        if text:
            for path, wid in Thumb.path_to_wid.items():
                if text in path:
                    self.select_new_widget(wid)
                    break

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        wid: Thumb | ThumbFolder 

        if a0.modifiers() & Qt.KeyboardModifier.ControlModifier:

            if a0.key() == Qt.Key.Key_Up:
                root = os.path.dirname(JsonData.root)
                if root != os.sep:
                    SignalsApp.all_.new_history_item.emit(root)
                    SignalsApp.all_.load_standart_grid.emit(root)

            elif  a0.key() == Qt.Key.Key_Down:
                wid = self.cell_to_wid.get(self.curr_cell)
                self.open_in_view(wid)

            elif a0.key() == Qt.Key.Key_I:
                wid = self.cell_to_wid.get(self.curr_cell)
                OpenWin.info(Utils.get_main_win(), wid.src)

            elif a0.key() == Qt.Key.Key_Equal:
                new_value = Dynamic.pixmap_size_ind + 1
                if new_value <= len(ThumbData.PIXMAP_SIZE) - 1:
                    SignalsApp.all_.move_slider.emit(new_value)

            elif a0.key() == Qt.Key.Key_Minus:
                new_value = Dynamic.pixmap_size_ind - 1
                if new_value >= 0:
                    SignalsApp.all_.move_slider.emit(new_value)

            elif a0.key() == Qt.Key.Key_D:
                self.open_find_here_win()

        elif a0.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return):
            wid = self.cell_to_wid.get(self.curr_cell)
            if wid:
                self.open_in_view(wid)

        elif a0.key() in (
            Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down
        ):

            offsets = {
                Qt.Key.Key_Left: (0, -1),
                Qt.Key.Key_Right: (0, 1),
                Qt.Key.Key_Up: (-1, 0),
                Qt.Key.Key_Down: (1, 0)
            }

            offset = offsets.get(a0.key())
            coords = (
                self.curr_cell[0] + offset[0], 
                self.curr_cell[1] + offset[1]
            )

            self.select_new_widget(coords)

        elif a0.key() in (
            Qt.Key.Key_0, Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3,
            Qt.Key.Key_4, Qt.Key.Key_5
        ):

            self.set_rating(a0.key())
        
        return super().keyPressEvent(a0)

    def mouseReleaseEvent(self, a0: QMouseEvent | None) -> None:
        self.remove_selection()

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:
        self.remove_selection()

        menu = QMenu(parent=self)

        create_folder = CreateFolder(
            menu=menu,
            window=self.window()
        )
        menu.addAction(create_folder)

        menu.addSeparator()

        info = Info(menu, JsonData.root)
        menu.addAction(info)

        reveal = RevealInFinder(parent=menu, src=JsonData.root)
        menu.addAction(reveal)

        copy_ = CopyPath(parent=menu, src=JsonData.root)
        menu.addAction(copy_)

        menu.addSeparator()

        if JsonData.root in JsonData.favs:
            cmd_ = lambda: self.fav_cmd(-1)
            self.fav_action = FavRemove(menu, JsonData.root)
            self.fav_action._clicked.connect(cmd_)
            menu.addAction(self.fav_action)

        else:
            cmd_ = lambda: self.fav_cmd(+1)
            self.fav_action = FavAdd(menu, JsonData.root)
            self.fav_action._clicked.connect(cmd_)
            menu.addAction(self.fav_action)

        menu.addSeparator()

        change_view = ChangeView(menu, JsonData.root)
        menu.addMenu(change_view)

        sort_menu = SortMenu(parent=menu)
        menu.addMenu(sort_menu)

        menu.addSeparator()

        upd_ = UpdateGrid(menu, JsonData.root)
        menu.addAction(upd_)

        find_here = FindHere(parent=menu)
        find_here.clicked_.connect(self.open_find_here_win)
        menu.addAction(find_here)

        menu.exec_(self.mapToGlobal(a0.pos()))

    def dragMoveEvent(self, a0):
        pos = a0.pos()
        global_pos = self.mapToGlobal(pos)
        widget = QApplication.widgetAt(global_pos) 

        if isinstance(widget, ThumbFolder):
            self.select_new_widget(data=widget)

    def dragEnterEvent(self, a0):
        a0.acceptProposedAction()

    def dropEvent(self, a0):

        # вычисляем, на какой виджет был перетянут объект
        # допустимы ThumbFolder, GridStandart(QWidget)
        pos = a0.pos()
        global_pos = self.mapToGlobal(pos)
        widget = QApplication.widgetAt(global_pos)

        # место, куда будет скопирован перетянутый объект,
        # ThumbFolder.src или JsonData.root
        dest = None

        # Thumb / ThumbFolder > QFrame (self.img_wid) > USvgWiаdget
        if isinstance(widget, USvgWidget):
            widget = widget.parent().parent()

        if isinstance(widget, ThumbFolder):
            dest = widget.src

        elif isinstance(widget, QWidget):
            dest = JsonData.root

        # Определяем источник данных:
        # Если в mimeData содержится URL, значит, данные были перетянуты
        # извне приложения (например, из Finder).
        # Если mimeData содержит только обычный текст (plain text),
        # то это данные, перетянутые из виджета Thumb.

        if a0.mimeData().hasUrls():
            urls = [
                i.toLocalFile()
                for i in a0.mimeData().urls()
            ]
        
        elif a0.mimeData().hasText():
            urls = [
                a0.mimeData().text()
            ]
        
        if dest:

            for url_ in urls:

                if os.path.isdir(url_):
                    continue


                self.task_ = FileCopyThread(
                    src=url_,
                    dest=dest
                    )
                
                self.win_copy = WinCopy(
                    src=url_,
                    dest=dest
                )

                Utils.center_win(
                    parent=self.window(),
                    child=self.win_copy
                )

                self.task_.signals_.finished_.connect(
                    self.win_copy.close
                )

                self.task_.signals_.finished_.connect(
                    lambda: SignalsApp.all_.load_standart_grid.emit(
                        JsonData.root
                    )
                )

                self.win_copy.show()
                UThreadPool.start(runnable=self.task_)
