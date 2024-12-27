import os

import sqlalchemy
from PyQt5.QtCore import QMimeData, Qt, QTimer, QUrl, pyqtSignal
from PyQt5.QtGui import (QContextMenuEvent, QDrag, QKeyEvent, QMouseEvent,
                         QPixmap, QCursor)
from PyQt5.QtWidgets import (QApplication, QFrame, QGridLayout, QLabel,
                             QScrollArea, QVBoxLayout, QWidget)
from sqlalchemy.exc import IntegrityError, OperationalError

from cfg import Dynamic, JsonData, Static, ThumbData
from database import CACHE, ColumnNames, Dbase, OrderItem
from signals import SignalsApp
from utils import URunnable, UThreadPool, Utils

from ._actions import (ChangeView, CopyPath, CreateFolder, DeleteFinderItem,
                       FavAdd, FavRemove, FindHere, Info, OpenInApp,
                       RatingMenu, RevealInFinder, ShowInFolder, SortMenu,
                       UpdateGrid, View)
from ._base import BaseMethods, OpenWin, UMenu, USvgWidget
from ._copy_files import WinCopyFiles
from .list_file_system import ListFileSystem
from .win_find_here import WinFindHere

SELECTED = "selected"
FONT_SIZE = "font-size: 11px;"
RAD = "border-radius: 4px"
IMG_WID_ATTR = "img_wid_attr"
SQL_ERRORS = (OperationalError, IntegrityError)
WID_UNDER_MOUSE = "win_under_mouse"

KEY_RATING = {
    Qt.Key.Key_0: 0,
    Qt.Key.Key_1: 1,
    Qt.Key.Key_2: 2,
    Qt.Key.Key_3: 3,
    Qt.Key.Key_4: 4,
    Qt.Key.Key_5: 5
}

KEY_NAVI = {
    Qt.Key.Key_Left: (0, -1),
    Qt.Key.Key_Right: (0, 1),
    Qt.Key.Key_Up: (-1, 0),
    Qt.Key.Key_Down: (1, 0)
}


class UpdateThumbData(URunnable):
    def __init__(self, name: str, values: dict, cmd_: callable):

        super().__init__()
        self.cmd_ = cmd_
        self.name = name
        self.values = values

    @URunnable.set_running_state
    def run(self):
        stmt = sqlalchemy.update(CACHE)
        stmt = stmt.where(CACHE.c.name == Utils.hash_filename(filename=self.name))
        stmt = stmt.values(**self.values)
        
        db = os.path.join(JsonData.root, Static.DB_FILENAME)
        dbase = Dbase()
        engine = dbase.create_engine(path=db)

        if engine is None:
            return

        conn = engine.connect()

        try:
            conn.execute(stmt)
            conn.commit()
            self.finalize()

        except SQL_ERRORS as e:
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
        self.setStyleSheet(FONT_SIZE)

    def set_text(self, wid: OrderItem) -> list[str]:
        name: str | list = wid.name
        max_row = ThumbData.MAX_ROW[Dynamic.pixmap_size_ind]
        lines: list[str] = []

        if len(name) > max_row:

            first_line = name[:max_row]
            second_line = name[max_row:]

            if len(second_line) > max_row:
                second_line = self.short_text(second_line, max_row)

            lines.append(first_line)
            lines.append(second_line)

        else:
            name = lines.append(name)

        self.setText("\n".join(lines))

    def short_text(self, text: str, max_row: int):
        return f"{text[:max_row - 10]}...{text[-7:]}"


class RatingWid(QLabel):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(FONT_SIZE)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_text(self, wid: OrderItem):
        text = Static.STAR_SYM * wid.rating
        self.setText(text)


class Thumb(OrderItem, QFrame):
    clicked_ = pyqtSignal()
    control_clicked = pyqtSignal()
    shift_clicked = pyqtSignal()
    r_clicked = pyqtSignal()
    mouse_moved = pyqtSignal()

    open_in_view = pyqtSignal()
    text_changed = pyqtSignal()

    path_to_wid: dict[str, "Thumb"] = {}

    pixmap_size = 0
    thumb_w = 0
    thumb_h = 0

    def __init__(self, src: str, size: int, mod: int, rating: int):

        QFrame.__init__(self, parent=None)
        OrderItem.__init__(self, src=src, size=size, mod=mod, rating=rating)

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

        self.rating_wid = RatingWid()
        self.v_lay.addWidget(self.rating_wid, alignment=Qt.AlignmentFlag.AlignCenter)

        for i in (self.img_frame, self.text_wid, self.rating_wid):
            i.mouseReleaseEvent = self.mouse_release_ev
            i.mousePressEvent = self.mouse_press_ev
            i.mouseMoveEvent = self.mouse_move_ev
            i.mouseDoubleClickEvent = self.mouse_double_click_ev
            i.contextMenuEvent = self.context_menu_ev

        self.setup()
        self.set_no_frame()

        # self.setStyleSheet("background: gray;")

    @classmethod
    def calculate_size(cls):
        ind = Dynamic.pixmap_size_ind
        cls.pixmap_size = ThumbData.PIXMAP_SIZE[ind]
        cls.thumb_w = ThumbData.THUMB_W[ind]
        cls.thumb_h = ThumbData.THUMB_H[ind]

    def set_pixmap(self, pixmap: QPixmap):
        self.svg_wid.deleteLater()

        self.img_wid = QLabel()

        self.img_wid.setPixmap(
            Utils.pixmap_scale(pixmap, Thumb.pixmap_size)
        )
    
        self.img_frame_lay.addWidget(
            self.img_wid,
            alignment=Qt.AlignmentFlag.AlignCenter
        )

        self.img = pixmap
        setattr(self, IMG_WID_ATTR, True)

    def setup(self):

        # при первой инициации нужно установить текст в виджеты
        for i in (self.text_wid, self.rating_wid):
            i.set_text(self)

        self.setFixedSize(
            Thumb.thumb_w,
            Thumb.thumb_h
        )

        # рамка вокруг pixmap при выделении Thumb
        self.img_frame.setFixedSize(
            Thumb.pixmap_size + ThumbData.OFFSET,
            Thumb.pixmap_size + ThumbData.OFFSET
        )

        if hasattr(self, IMG_WID_ATTR):

            self.img_wid.setPixmap(
                Utils.pixmap_scale(
                    pixmap=self.img,
                    size=Thumb.pixmap_size
                )
            )
        else:
            self.svg_wid.setFixedSize(
                Thumb.pixmap_size,
                Thumb.pixmap_size
            )

    def set_frame(self):

        self.text_wid.setStyleSheet(
            f"""
                background: {Static.BLUE};
                {FONT_SIZE};
                {RAD};
                padding: 2px;
            """
        )

        self.img_frame.setStyleSheet(
            f"""
                background: {Static.GRAY_UP_BTN};
                {FONT_SIZE};
                {RAD};
            """
        )

    def set_no_frame(self):
    
        self.text_wid.setStyleSheet(
            f"""
                background: transparent;
                {FONT_SIZE};
                {RAD};
                padding: 2px;
            """
        )
    
        self.img_frame.setStyleSheet(
            f"""
                background: transparent;
                {FONT_SIZE};
                {RAD};
            """
        )

    def add_base_actions(self, menu: UMenu):

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

        rating_menu = RatingMenu(parent=menu, src=self.src, rating=self.rating)
        rating_menu._clicked.connect(self.set_new_rating)
        menu.addMenu(rating_menu)

        menu.addSeparator()

        delete_item = DeleteFinderItem(menu=menu, path=self.src)
        menu.addAction(delete_item)

    def set_rating(self, rating: int):

        self.rating = rating
        self.rating_wid.set_text(wid=self)
        self.text_changed.emit()

    def set_new_rating(self, rating: int):

        self.rating = rating
        self.rating_wid.set_text(wid=self)
        self.text_changed.emit()

        def cmd_():
            self.rating = rating
            self.rating_wid.set_text(wid=self)
            self.text_changed.emit()

        self.task_ = UpdateThumbData(
            name=self.name,
            values={ColumnNames.RATING: rating},
            cmd_=cmd_
        )

        UThreadPool.start(self.task_)

    def mouse_release_ev(self, a0: QMouseEvent | None) -> None:

        if a0.button() & Qt.MouseButton.LeftButton:
    
            if a0.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self.control_clicked.emit()

            elif a0.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.shift_clicked.emit()

            else:
                self.clicked_.emit()

    def mouse_press_ev(self, a0: QMouseEvent | None) -> None:
        if a0.button() == Qt.MouseButton.LeftButton:
            self.start_pos = a0.pos()

    def mouse_move_ev(self, a0: QMouseEvent | None) -> None:

        if hasattr(self, "start_pos"):
            distance = (a0.pos() - self.start_pos).manhattanLength()

            if distance < QApplication.startDragDistance():
                return

        self.mouse_moved.emit()

    def mouse_double_click_ev(self, a0: QMouseEvent | None) -> None:
        self.open_in_view.emit()

    def context_menu_ev(self, a0: QContextMenuEvent | None) -> None:
        self.r_clicked.emit()
        # self.clicked_.emit()
        # context_menu = UMenu(self)
        # self.add_base_actions(context_menu)
        # context_menu.exec_(self.mapToGlobal(a0.pos()))


class ThumbFolder(Thumb):
    def __init__(self, src: str, size: int, mod: int, rating: int):
        super().__init__(src, size, mod, rating)

        self.svg_path = Static.FOLDER_SVG
        img_wid = self.img_frame.findChild(USvgWidget)
        img_wid.load(self.svg_path)

        for i in (self.img_frame, self.text_wid, self.rating_wid):
            i.contextMenuEvent = self.mouse_r_click

    def fav_cmd(self, offset: int):
        self.fav_action.triggered.disconnect()
        if 0 + offset == 1:
            SignalsApp.instance.fav_cmd.emit({"cmd": "add", "src": self.src})
            self.fav_action.setText("Удалить из избранного")
            self.fav_action.triggered.connect(lambda: self.fav_cmd(-1))
        else:
            SignalsApp.instance.fav_cmd.emit({"cmd": "del", "src": self.src})
            self.fav_action.setText("Добавить в избранное")
            self.fav_action.triggered.connect(lambda: self.fav_cmd(+1))

    def mouse_r_click(self, a0: QContextMenuEvent | None) -> None:
        self.clicked_.emit()

        menu = UMenu(parent=self)

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

        rating_menu = RatingMenu(parent=menu, src=self.src, rating=self.rating)
        rating_menu._clicked.connect(self.set_new_rating)
        menu.addMenu(rating_menu)

        menu.addSeparator()

        delete_item = DeleteFinderItem(menu=menu, path=self.src)
        menu.addAction(delete_item)

        menu.exec_(self.mapToGlobal(a0.pos()))

 
class ThumbSearch(Thumb):
    def __init__(self, src: str, size: int, mod: int, rating: int):
        super().__init__(src, size, mod, rating)

        for i in (self.img_frame, self.text_wid, self.rating_wid):
            i.contextMenuEvent = self.mouse_r_click

    def show_in_folder_cmd(self):

        SignalsApp.instance.load_standart_grid_cmd(
            path=os.path.dirname(self.src),
            prev_path=self.src
        )

    def mouse_r_click(self, a0: QContextMenuEvent | None) -> None:
        self.clicked_.emit()
    
        menu_ = UMenu(parent=self)
        self.add_base_actions(menu_)
        menu_.addSeparator()

        show_in_folder = ShowInFolder(parent=menu_, src=self.src)
        show_in_folder._clicked.connect(self.show_in_folder_cmd)
        menu_.addAction(show_in_folder)

        menu_.exec_(self.mapToGlobal(a0.pos()))


class GridWid(QWidget):
    def __init__(self):
        super().__init__()


class Grid(BaseMethods, QScrollArea):

    def __init__(self, width: int, prev_path: str = None):
        Thumb.path_to_wid.clear()

        QScrollArea.__init__(self)
        BaseMethods.__init__(self)

        self.setAcceptDrops(True)
        self.setWidgetResizable(True)

        self.prev_path = prev_path
        self.selected_widgets: list[Thumb] = []
        self.curr_cell: tuple = None
        self.cell_to_wid: dict[tuple, Thumb] = {}
        self.ordered_widgets: list[OrderItem | Thumb | ThumbFolder | ThumbSearch] = []
        self.ww = width

        # Посколько сетка может множество раз перезагружаться
        # прежде нужно отключить прошлые подключения чтобы не было
        # дублирования подклювчений
        SignalsApp.disconnect_grid()

        SignalsApp.instance.resize_grid.connect(self.resize_)
        SignalsApp.instance.sort_grid.connect(self.order_)
        SignalsApp.instance.filter_grid.connect(self.filter_)
        SignalsApp.instance.move_to_wid.connect(self.select_one_wid)

        self.main_wid = GridWid()
        self.setWidget(self.main_wid)

        flags = Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(Static.GRID_SPACING)
        self.grid_layout.setAlignment(flags)

        self.main_wid.setLayout(self.grid_layout)

    def select_one_wid(self, wid: Thumb):

        # важно передать сюда именно виджет, который содержит row, col
        # а не напрямую передавать row, col, так как при rearrange
        # row col виджета будут меняться

        for i in self.selected_widgets:
            i.set_no_frame()

        wid.set_frame()
        self.curr_cell = (wid.row, wid.col)
        self.ensureWidgetVisible(wid)
        self.selected_widgets = [wid]
        self.set_bottom_path(src=wid.src)

    def set_bottom_path(self, src: str):
        # через таймер чтобы функция не блокировалась зажатой клавишей мыши
        cmd_ = lambda: SignalsApp.instance.bar_bottom_cmd.emit(
            {"src" : src}
        )
        QTimer.singleShot(100, cmd_)
    
    def order_(self):
        self.ordered_widgets = OrderItem.sort_items(self.ordered_widgets)
        
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

    def rearrange(self, width: int = None):

        if width:
            self.ww = width
            col_count = Utils.get_clmn_count(width)
        else:
            col_count = Utils.get_clmn_count(self.ww)

        self.cell_to_wid.clear()
        self.curr_cell = None
        for i in self.selected_widgets:
            i.set_no_frame()

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

        if self.prev_path:
            wid = Thumb.path_to_wid.get(self.prev_path)
            self.select_one_wid(wid=wid)
            QTimer.singleShot(500, lambda: self.ensureWidgetVisible(wid))

    def add_widget_data(self, wid: Thumb, row: int, col: int):
        wid.row, wid.col = row, col
        self.cell_to_wid[row, col] = wid
        Thumb.path_to_wid[wid.src] = wid
        self.ordered_widgets.append(wid)

    def open_in_view(self, wid: Thumb):

        if wid is None:
            return

        elif wid.type_ == Static.FOLDER_TYPE:
            
            SignalsApp.instance.new_history_item.emit(wid.src)
            SignalsApp.instance.load_standart_grid_cmd(
                path=wid.src,
                prev_path=None
            )

        else:
            OpenWin.view(
                parent=self.window(),
                src=wid.src
            )

    def select_after_list(self):
        wid = Thumb.path_to_wid.get(ListFileSystem.last_selection)

        if isinstance(wid, Thumb):
            self.select_one_wid(wid)
            self.ensureWidgetVisible(wid)
            ListFileSystem.last_selection = None

    def fav_cmd(self, offset: int):
        self.fav_action.triggered.disconnect()
        if 0 + offset == 1:

            SignalsApp.instance.fav_cmd.emit({"cmd": "add", "src": JsonData.root})
            self.fav_action.setText("Удалить из избранного")
            self.fav_action.triggered.connect(lambda: self.fav_cmd(-1))

        else:
            SignalsApp.instance.fav_cmd.emit({"cmd": "del", "src": JsonData.root})
            self.fav_action.setText("Добавить в избранное")
            self.fav_action.triggered.connect(lambda: self.fav_cmd(+1))

    def open_find_here_win(self, *args):
        self.find_here_win = WinFindHere()
        self.find_here_win.finished_.connect(self.find_here_cmd)
        Utils.center_win(parent=self.window(), child=self.find_here_win)
        self.find_here_win.show()

    def find_here_cmd(self, text: str):
        if text:
            for path, wid in Thumb.path_to_wid.items():
                if text in path:
                    self.select_one_wid(wid)
                    break

    def control_clicked(self, wid: Thumb):

        if wid in self.selected_widgets:
            self.selected_widgets.remove(wid)
            wid.set_no_frame()

        else:
            self.selected_widgets.append(wid)
            wid.set_frame()

        self.curr_cell = (wid.row, wid.col)

    def shift_clicked(self, wid: Thumb):

        if self.curr_cell is None:
            self.select_one_wid(wid)
            return
        
        coords = list(self.cell_to_wid)

        if coords.index((wid.row, wid.col)) > coords.index(self.curr_cell):
            start = coords.index(self.curr_cell)
            end = coords.index((wid.row, wid.col))
            coords = coords[start : end + 1]

        else:
            start = coords.index((wid.row, wid.col))
            end = coords.index(self.curr_cell)
            coords = coords[start : end]

        for i in coords:

            wid_ = self.cell_to_wid.get(i)

            if wid_ not in self.selected_widgets:
                wid_.set_frame()
                self.selected_widgets.append(wid_)

    def drag_thumb(self, wid: Thumb):

        if len(self.selected_widgets) < 2:
            self.select_one_wid(wid)

        drag = QDrag(self)
        mime_data = QMimeData()

        urls = []

        key = [False, False]

        result_map = {
            (True, True): QPixmap(Static.FOLDER_FILE_SVG),
            (True, False): QPixmap(Static.FOLDER_SVG),
            (False, True): QPixmap(Static.IMG_SVG)
        }

        for wid_ in self.selected_widgets:
            urls.append(QUrl.fromLocalFile(wid_.src))

            if wid_.type_ == Static.FOLDER_TYPE:
                key[0] = True
            else:
                key[1] = True

        mime_data.setUrls(urls)
        drag.setPixmap(result_map.get(tuple(key)))
        drag.setMimeData(mime_data)

        drag.exec_(Qt.DropAction.CopyAction)

    def context_thumb(self, wid: Thumb):

        if wid not in self.selected_widgets:
            self.select_one_wid(wid=wid)

        files = [
            i.src
            for i in self.selected_widgets
        ]

        menu = UMenu()

        view_action = View(parent=menu, src=wid.src)
        view_action._clicked.connect(lambda: self.open_in_view(wid=wid))
        menu.addAction(view_action)

        open_menu = OpenInApp(parent=menu, src=wid.src)
        menu.addMenu(open_menu)

        menu.addSeparator()

        info = Info(parent=menu, src=wid.src)
        menu.addAction(info)

        show_in_finder_action = RevealInFinder(parent=menu, src=files)
        menu.addAction(show_in_finder_action)

        copy_path = CopyPath(parent=menu, src=wid.src)
        menu.addAction(copy_path)

        menu.addSeparator()

        rating_menu = RatingMenu(parent=menu, src=wid.src, rating=wid.rating)
        rating_menu._clicked.connect(self.set_rating_wid)
        menu.addMenu(rating_menu)

        menu.addSeparator()

        delete_item = DeleteFinderItem(menu=menu, path=wid.src)
        menu.addAction(delete_item)

        menu.show_custom()

    def set_rating_wid(self, rating: int):

        for i in self.selected_widgets:
            i.set_new_rating(rating=rating)

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        wid: Thumb | ThumbFolder 

        if a0.modifiers() & Qt.KeyboardModifier.ControlModifier:

            if a0.key() == Qt.Key.Key_Up:

                old_root = JsonData.root
                root = os.path.dirname(JsonData.root)

                if root != os.sep:

                    SignalsApp.instance.new_history_item.emit(root)

                    SignalsApp.instance.load_standart_grid_cmd(
                        path=root,
                        prev_path=old_root
                    )

            elif a0.key() == Qt.Key.Key_Down:
                wid = self.cell_to_wid.get(self.curr_cell)
                if wid:
                    self.open_in_view(wid)

            elif a0.key() == Qt.Key.Key_I:
                wid = self.cell_to_wid.get(self.curr_cell)
                if wid:
                    OpenWin.info(parent=self.window(), src=wid.src)
                else:
                    OpenWin.info(parent=self.window(), src=JsonData.root)

            elif a0.key() == Qt.Key.Key_Equal:
                new_value = Dynamic.pixmap_size_ind + 1
                if new_value <= len(ThumbData.PIXMAP_SIZE) - 1:
                    SignalsApp.instance.move_slider.emit(new_value)

            elif a0.key() == Qt.Key.Key_Minus:
                new_value = Dynamic.pixmap_size_ind - 1
                if new_value >= 0:
                    SignalsApp.instance.move_slider.emit(new_value)

            elif a0.key() == Qt.Key.Key_D:
                self.open_find_here_win()

            elif a0.key() == Qt.Key.Key_A:
                self.selected_widgets.clear()
                for cell, wid in self.cell_to_wid.items():
                    wid.set_frame()
                    self.selected_widgets.append(wid)
                    

        elif a0.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return):
            wid = self.cell_to_wid.get(self.curr_cell)
            if wid:
                self.open_in_view(wid)

        elif a0.key() in KEY_NAVI:

            offset = KEY_NAVI.get(a0.key())

            if self.curr_cell is None:
                self.curr_cell = (0, 0)

            coords = (
                self.curr_cell[0] + offset[0], 
                self.curr_cell[1] + offset[1]
            )

            wid = self.cell_to_wid.get(coords)

            if wid:
                self.select_one_wid(wid=wid)

        elif a0.key() in KEY_RATING:
    
            rating = KEY_RATING.get(a0.key())
            self.set_rating_wid(rating=rating)
        
        return super().keyPressEvent(a0)

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:

        for i in self.selected_widgets:
            i.set_no_frame()

        cmd_ = lambda: SignalsApp.instance.bar_bottom_cmd.emit(
            {"src": JsonData.root}
        )

        QTimer.singleShot(100, cmd_)

        menu = UMenu(parent=self)

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

    def mouseReleaseEvent(self, a0):

        if a0.modifiers() in (
            Qt.KeyboardModifier.ShiftModifier,
            Qt.KeyboardModifier.ControlModifier
        ):
            
            return

        for i in self.selected_widgets:
            i.set_no_frame()

        self.selected_widgets.clear()
        self.set_bottom_path(src=JsonData.root)
        self.curr_cell = None

    def dragEnterEvent(self, a0):
        a0.acceptProposedAction()

    def dragMoveEvent(self, a0):
        wid = self.childAt(a0.pos())
        
        if isinstance(wid, QFrame):
            wid = wid.parent()

        elif isinstance(wid, USvgWidget):
            wid = wid.parent().parent()

        if isinstance(wid, ThumbFolder):
            self.select_one_wid(wid)
            setattr(self, WID_UNDER_MOUSE, wid)
            a0.acceptProposedAction()

        elif isinstance(wid, GridWid):

            for i in self.selected_widgets:
                if i.type_ == Static.FOLDER_TYPE:
                    i.set_no_frame()

            setattr(self, WID_UNDER_MOUSE, wid)
            a0.acceptProposedAction()

    def dropEvent(self, a0):

        if hasattr(self, WID_UNDER_MOUSE):
            
            wid: ThumbFolder | QWidget = getattr(self, WID_UNDER_MOUSE)

            if isinstance(wid, ThumbFolder):
                dest = wid.src

            elif isinstance(wid, GridWid):
                dest = JsonData.root

            self.dia = WinCopyFiles(mime_data=a0.mimeData(), dest=dest)
            Utils.center_win(parent=self.window(), child=self.dia)
            QTimer.singleShot(1000, self.dia.custom_show)
