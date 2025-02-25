import os

import sqlalchemy
from PyQt5.QtCore import QMimeData, Qt, QTimer, QUrl, pyqtSignal
from PyQt5.QtGui import (QContextMenuEvent, QDrag, QKeyEvent, QMouseEvent,
                         QPixmap)
from PyQt5.QtWidgets import (QApplication, QFrame, QGridLayout, QLabel,
                             QScrollArea, QVBoxLayout, QWidget)
from sqlalchemy.exc import IntegrityError, OperationalError

from cfg import Dynamic, JsonData, Static, ThumbData
from database import CACHE, ColumnNames, Dbase, OrderItem
from signals import SignalsApp
from utils import URunnable, UThreadPool, Utils

from ._actions import (ChangeView, CopyFilesAction, CopyPath, FavAdd,
                       FavRemove, Info, OpenInApp, PasteFilesAction,
                       RatingMenu, RemoveFilesAction, RevealInFinder,
                       ShowInFolder, SortMenu, TagMenu, UpdateGrid, View)
from ._base import BaseMethods, OpenWin, UMenu, USvgWidget
from .list_file_system import ListFileSystem
from .win_copy_files import WinCopyFiles
from .win_remove_files import WinRemoveFiles

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
    Qt.Key.Key_5: 5,
    Qt.Key.Key_6: 6,
    Qt.Key.Key_7: 7,
    Qt.Key.Key_8: 8,
    Qt.Key.Key_9: 9
}

KEY_NAVI = {
    Qt.Key.Key_Left: (0, -1),
    Qt.Key.Key_Right: (0, 1),
    Qt.Key.Key_Up: (-1, 0),
    Qt.Key.Key_Down: (1, 0)
}

RATINGS = {
    # для старого рейтинга, когда число рейтинга было от 0 до 5
    0: "",
    1: Static.STAR_SYM,
    2: Static.STAR_SYM * 2,
    3: Static.STAR_SYM * 3,
    4: Static.STAR_SYM * 4,
    5: Static.STAR_SYM * 5,

    # для нового рейтинга, где первое число - тег, второе - рейтинг
    # 6, 7, 8 - теги
    # 9 - без тега
    90: "",
    91: Static.STAR_SYM,
    92: Static.STAR_SYM * 2,
    93: Static.STAR_SYM * 3,
    94: Static.STAR_SYM * 4,
    95: Static.STAR_SYM * 5,
    
    # теги
    6: Static.DEINED_SYM + " " + Static.DEINED_T,
    7: Static.REVIEW_SYM + " " + Static.REVIEW_T,
    8: Static.APPROVED_SYM + " " + Static.APPROVED_T,
    9: "",

    60: Static.DEINED_SYM + " " + Static.DEINED_T,
    61: Static.DEINED_SYM + " " + Static.STAR_SYM,
    62: Static.DEINED_SYM + " " + Static.STAR_SYM * 2,
    63: Static.DEINED_SYM + " " + Static.STAR_SYM * 3,
    64: Static.DEINED_SYM + " " + Static.STAR_SYM * 4,
    65: Static.DEINED_SYM + " " + Static.STAR_SYM * 5,

    70: Static.REVIEW_SYM + " " + Static.REVIEW_T,
    71: Static.REVIEW_SYM + " " + Static.STAR_SYM,
    72: Static.REVIEW_SYM + " " + Static.STAR_SYM * 2,
    73: Static.REVIEW_SYM + " " + Static.STAR_SYM * 3,
    74: Static.REVIEW_SYM + " " + Static.STAR_SYM * 4,
    75: Static.REVIEW_SYM + " " + Static.STAR_SYM * 5,

    80: Static.APPROVED_SYM + " " + Static.APPROVED_T,
    81: Static.APPROVED_SYM + " " + Static.STAR_SYM,
    82: Static.APPROVED_SYM + " " + Static.STAR_SYM * 2,
    83: Static.APPROVED_SYM + " " + Static.STAR_SYM * 3,
    84: Static.APPROVED_SYM + " " + Static.STAR_SYM * 4,
    85: Static.APPROVED_SYM + " " + Static.STAR_SYM * 5,

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


class ImgFrame(QFrame):
    def __init__(self):
        super().__init__()

    def mouseReleaseEvent(self, a0):
        return super().mouseReleaseEvent(a0)
    
    def mousePressEvent(self, a0):
        return super().mousePressEvent(a0)

    def mouseMoveEvent(self, a0):
        return super().mouseMoveEvent(a0)
    
    def mouseDoubleClickEvent(self, a0):
        return super().mouseDoubleClickEvent(a0)
    
    def contextMenuEvent(self, a0):
        return super().contextMenuEvent(a0)


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

    def mouseReleaseEvent(self, a0):
        return super().mouseReleaseEvent(a0)
    
    def mousePressEvent(self, a0):
        return super().mousePressEvent(a0)

    def mouseMoveEvent(self, a0):
        return super().mouseMoveEvent(a0)
    
    def mouseDoubleClickEvent(self, a0):
        return super().mouseDoubleClickEvent(a0)
    
    def contextMenuEvent(self, a0):
        return super().contextMenuEvent(a0)


class RatingWid(QLabel):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(FONT_SIZE)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_text(self, wid: OrderItem):
        text = RATINGS[wid.rating].strip()
        self.setText(text)

    def mouseReleaseEvent(self, a0):
        return super().mouseReleaseEvent(a0)
    
    def mousePressEvent(self, a0):
        return super().mousePressEvent(a0)

    def mouseMoveEvent(self, a0):
        return super().mouseMoveEvent(a0)
    
    def mouseDoubleClickEvent(self, a0):
        return super().mouseDoubleClickEvent(a0)
    
    def contextMenuEvent(self, a0):
        return super().contextMenuEvent(a0)


class Thumb(OrderItem, QFrame):
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


        self.img_frame = ImgFrame()
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

    def set_rating(self, rating: int):
        # устанавливается значение из бд
        self.rating = rating
        self.rating_wid.set_text(wid=self)
        self.text_changed.emit()

    def set_new_rating(self, value: int):

        if value > 5:
            rating = self.rating % 10
            tag = value
        else:
            tag = self.rating // 10
            rating = value

        total = tag * 10 + rating


        self.rating = total
        self.rating_wid.set_text(wid=self)
        self.text_changed.emit()

        def cmd_():
            self.rating = total
            self.rating_wid.set_text(wid=self)
            self.text_changed.emit()

        self.task_ = UpdateThumbData(
            name=self.name,
            values={ColumnNames.RATING: total},
            cmd_=cmd_
        )

        UThreadPool.start(self.task_)


class ThumbFolder(Thumb):
    def __init__(self, src: str, size: int, mod: int, rating: int):
        super().__init__(src, size, mod, rating)

        self.svg_path = Static.FOLDER_SVG
        img_wid = self.img_frame.findChild(USvgWidget)
        img_wid.load(self.svg_path)


class ThumbSearch(Thumb):
    def __init__(self, src: str, size: int, mod: int, rating: int):
        super().__init__(src, size, mod, rating)

    def show_in_folder_cmd(self):
        root = os.path.dirname(self.src)
        SignalsApp.instance.load_standart_grid_cmd(
            path=root,
            prev_path=self.src
        )


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
        self.cell_to_wid: dict[tuple, Thumb] = {}
        self.ordered_widgets: list[OrderItem | Thumb | ThumbFolder | ThumbSearch] = []
        self.ww = width

        # Посколько сетка может множество раз перезагружаться
        # прежде нужно отключить прошлые подключения чтобы не было
        # дублирования подклювчений
        SignalsApp.disconnect_grid()

        SignalsApp.instance.resize_grid.connect(self.resize_)
        SignalsApp.instance.filter_grid.connect(self.filter_)
        SignalsApp.instance.move_to_wid.connect(self.select_one_wid)

        self.main_wid = GridWid()
        self.setWidget(self.main_wid)

        flags = Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(Static.GRID_SPACING)
        self.grid_layout.setAlignment(flags)
        self.main_wid.setLayout(self.grid_layout)

        # отложенное подключение клика мышки нужно для того
        # избежать бага выделения виджета, когда кликаешь на папку
        # описание бага:
        # когда кликаешь на папку, формируется новая сетка StandatGrid
        # и в том месте, где был клик по папке, выделяется новый виджет
        # с которого не снять выделение
        # короче попробуй сразу подключить mouseReleaseEvent и открой 
        # любую папку с кучей файлов
        QTimer.singleShot(200, self.set_mouseReleaseEvent)
        
    def set_mouseReleaseEvent(self):
        self.mouseReleaseEvent = self.custom_mouseReleaseEvent

    def select_one_wid(self, wid: Thumb):

        # важно передать сюда именно виджет, который содержит row, col
        # а не напрямую передавать row, col, так как при rearrange
        # row col виджета будут меняться

        if wid is None:
            return

        self.clear_selected_widgets()

        wid.set_frame()
        self.selected_widgets.append(wid)
        self.ensureWidgetVisible(wid)
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

                if Dynamic.rating_filter > 5:

                    # 6, 7, 8, 9 - теги
                    # получаем первую цифру из рейтинга,
                    # которая соответствует значению тега
                    # в старых версиях рейтинг однозначный, поэтому 
                    # мы получем ноль при делении. тогда присваиваем 
                    # значение тега 9, что соответствует "без тегов"
                    # например значение 65: 6 - тег, а 5 - рейтинг
                    # значение 5: 0 - тег, а 5 - рейтинг
                    wid_value = wid.rating // 10

                    if wid_value == 0:
                        wid_value = 9

                    if wid_value != Dynamic.rating_filter:
                        show_widget = False

                else:
                    # 0, 1, 2, 3, 4, 5 - рейтинг
                    # получаем вторую цифру, которая соответствует значению
                    # рейтинга
                    wid_value = wid.rating % 10
                    if wid_value != Dynamic.rating_filter:
                        show_widget = False

            if show_widget:
                wid.must_hidden = False
                wid.show()
            else:
                wid.must_hidden = True
                wid.hide()

        self.rearrange()

    def resize_(self, width: int = None):

        wid_src_list = []

        for i in self.selected_widgets:
            wid_src_list.append(i.src)

        Thumb.calculate_size()
        for wid in self.ordered_widgets:
            wid.setup()

        self.rearrange(width=width)

        for src, wid in Thumb.path_to_wid.items():
            if src in wid_src_list:
                wid.set_frame()

    def rearrange(self, width: int = None):

        if width:
            self.ww = width
            col_count = Utils.get_clmn_count(width)
        else:
            col_count = Utils.get_clmn_count(self.ww)

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

        if self.prev_path:
            wid = Thumb.path_to_wid.get(self.prev_path)
            self.select_one_wid(wid=wid)
            QTimer.singleShot(500, lambda: self.ensureWidgetVisible(wid))

    def add_widget_data(self, wid: Thumb, row: int, col: int):
        wid.row, wid.col = row, col
        self.cell_to_wid[row, col] = wid
        Thumb.path_to_wid[wid.src] = wid
        self.ordered_widgets.append(wid)

    def view_thumb_cmd(self, wid: Thumb):

        if wid is None:
            return

        elif wid.type_ == Static.FOLDER_TYPE:
            self.mouseReleaseEvent = None
            SignalsApp.instance.new_history_item.emit(wid.src)
            SignalsApp.instance.load_standart_grid_cmd(path=wid.src, prev_path=None)
            # cmd_ = lambda: SignalsApp.instance.load_standart_grid_cmd(path=wid.src, prev_path=None)
            # QTimer.singleShot(100, cmd_)

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

    def fav_cmd(self, offset: int, src: str):
        if 0 + offset == 1:
            SignalsApp.instance.fav_cmd.emit({"cmd": "add", "src": src})
        else:
            SignalsApp.instance.fav_cmd.emit({"cmd": "del", "src": src})

    def thumb_context_actions(self, menu: UMenu, wid: Thumb):

        urls = [
            i.src
            for i in self.selected_widgets
        ]

        view_action = View(parent=menu, src=wid.src)
        view_action._clicked.connect(lambda: self.view_thumb_cmd(wid=wid))
        menu.addAction(view_action)

        if wid.type_ != Static.FOLDER_TYPE:
            open_menu = OpenInApp(parent=menu, src=wid.src)
            menu.addMenu(open_menu)

        menu.addSeparator()

        info = Info(parent=menu, src=wid.src)
        menu.addAction(info)

        show_in_finder_action = RevealInFinder(parent=menu, src=urls)
        menu.addAction(show_in_finder_action)

        copy_path = CopyPath(parent=menu, src=urls)
        menu.addAction(copy_path)

        copy_files = CopyFilesAction(parent=menu, urls=urls)
        copy_files.clicked_.connect(self.copy_files)
        menu.addAction(copy_files)

        menu.addSeparator()

        if wid.type_ == Static.FOLDER_TYPE:

            if wid.src in JsonData.favs:
                cmd_ = lambda: self.fav_cmd(offset=-1, src=wid.src)
                fav_action = FavRemove(menu, wid.src)
                fav_action._clicked.connect(cmd_)
                menu.addAction(fav_action)

            else:
                cmd_ = lambda: self.fav_cmd(offset=1, src=wid.src)
                fav_action = FavAdd(menu, wid.src)
                fav_action._clicked.connect(cmd_)
                menu.addAction(fav_action)

            menu.addSeparator()

        rating_menu = RatingMenu(parent=menu, src=urls, rating=wid.rating)
        rating_menu._clicked.connect(self.set_rating_wid)
        menu.addMenu(rating_menu)

        tags_menu = TagMenu(parent=menu, src=urls, rating=wid.rating)
        tags_menu._clicked.connect(wid.set_new_rating)
        menu.addMenu(tags_menu)

        menu.addSeparator()

        if isinstance(wid, ThumbSearch):

            show_in_folder = ShowInFolder(parent=menu, src=wid.src)
            show_in_folder._clicked.connect(wid.show_in_folder_cmd)
            menu.addAction(show_in_folder)

            menu.addSeparator()

        menu.addSeparator()

        remove_files = RemoveFilesAction(parent=menu, urls=urls)
        remove_files.clicked_.connect(lambda: self.remove_files_cmd(urls=urls))
        menu.addAction(remove_files)

    def grid_context_actions(self, menu: UMenu):

        info = Info(menu, JsonData.root)
        menu.addAction(info)

        reveal = RevealInFinder(parent=menu, src=JsonData.root)
        menu.addAction(reveal)

        copy_ = CopyPath(parent=menu, src=JsonData.root)
        menu.addAction(copy_)

        menu.addSeparator()

        if JsonData.root in JsonData.favs:
            cmd_ = lambda: self.fav_cmd(offset=-1, src=JsonData.root)
            fav_action = FavRemove(menu, JsonData.root)
            fav_action._clicked.connect(cmd_)
            menu.addAction(fav_action)

        else:
            cmd_ = lambda: self.fav_cmd(offset=+1, src=JsonData.root)
            fav_action = FavAdd(menu, JsonData.root)
            fav_action._clicked.connect(cmd_)
            menu.addAction(fav_action)

        menu.addSeparator()

        change_view = ChangeView(menu, JsonData.root)
        menu.addMenu(change_view)

        sort_menu = SortMenu(parent=menu)
        menu.addMenu(sort_menu)

        menu.addSeparator()

        if Dynamic.files_to_copy:
            paste_files = PasteFilesAction(parent=menu)
            paste_files.clicked_.connect(self.paste_files)
            menu.addAction(paste_files)

        upd_ = UpdateGrid(menu, JsonData.root)
        menu.addAction(upd_)

        # col_count это аттрибут GridSearch
        # переназначаем действие upd_ (обновить сетку) на grid order
        if hasattr(self, "col_count"):
            upd_.disconnect()
            upd_.triggered.connect(self.order_)

    def set_rating_wid(self, rating: int):
        for i in self.selected_widgets:
            i.set_new_rating(value=rating)

    def get_wid_under_mouse(self, a0: QMouseEvent) -> None | Thumb:
        wid = QApplication.widgetAt(a0.globalPos())

        if isinstance(wid, (TextWidget, RatingWid, ImgFrame)):
            return wid.parent()
        elif isinstance(wid, (QLabel, USvgWidget)):
            return wid.parent().parent()
        else:
            return None
        
    def clear_selected_widgets(self):
        for i in self.selected_widgets:
            i.set_no_frame()
        self.selected_widgets.clear()

    def add_and_select_widget(self, wid: Thumb):
        if isinstance(wid, Thumb):
            self.selected_widgets.append(wid)
            wid.set_frame()

    def copy_files(self):
        Dynamic.files_to_copy.clear()

        for i in self.selected_widgets:
            Dynamic.files_to_copy.append(i.src)

    def paste_files(self):
        self.win_copy = WinCopyFiles()
        self.win_copy.show()

    def remove_files_cmd(self, urls: list[str]):
        self.rem_win = WinRemoveFiles(urls=urls)
        self.rem_win.show()

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        clicked_wid: Thumb | ThumbFolder 

        if a0.modifiers() & Qt.KeyboardModifier.ControlModifier:

            if a0.key() == Qt.Key.Key_V:
                self.paste_files()

            elif a0.key() == Qt.Key.Key_C:
                self.copy_files()

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
                clicked_wid = self.selected_widgets[-1]
                if clicked_wid:
                    self.select_one_wid(wid=clicked_wid)
                    self.view_thumb_cmd(clicked_wid)

            elif a0.key() == Qt.Key.Key_I:
                clicked_wid = self.selected_widgets[-1]
                if clicked_wid:
                    self.select_one_wid(wid=clicked_wid)
                    OpenWin.info(parent=self.window(), src=clicked_wid.src)
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

            elif a0.key() == Qt.Key.Key_A:
                self.clear_selected_widgets()
                for cell, clicked_wid in self.cell_to_wid.items():
                    clicked_wid.set_frame()
                    self.selected_widgets.append(clicked_wid)

        elif a0.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return):
            if self.selected_widgets:
                clicked_wid = self.selected_widgets[-1]
                if clicked_wid:
                    self.select_one_wid(wid=clicked_wid)
                    self.view_thumb_cmd(clicked_wid)

        elif a0.key() in KEY_NAVI:

            offset = KEY_NAVI.get(a0.key())

            # если не выделено ни одного виджета
            if not self.selected_widgets:
                wid = self.cell_to_wid.get((0, 0))
            else:
                wid = self.selected_widgets[-1]

            # если нет даже первого виджета значит сетка пуста
            if not wid:
                return

            coords = (
                wid.row + offset[0], 
                wid.col + offset[1]
            )

            clicked_wid = self.cell_to_wid.get(coords)

            if clicked_wid:
                self.select_one_wid(wid=clicked_wid)

        elif a0.key() in KEY_RATING:
    
            rating = KEY_RATING.get(a0.key())
            self.set_rating_wid(rating=rating)
        
        return super().keyPressEvent(a0)

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:

        cmd_ = lambda: SignalsApp.instance.bar_bottom_cmd.emit(
            {"src": JsonData.root}
        )

        QTimer.singleShot(100, cmd_)

        menu = UMenu(parent=self)
        clicked_wid = self.get_wid_under_mouse(a0=a0)

        # клик по пустому пространству
        if not clicked_wid:
            self.clear_selected_widgets()
            self.grid_context_actions(menu=menu)

        # клик по виджету
        else:

            # если не было выделено ни одного виджет ранее
            # то выделяем кликнутый
            if not self.selected_widgets:
                self.add_and_select_widget(wid=clicked_wid)

            # если есть выделенные виджеты, но кликнутый виджет не выделены
            # то снимаем выделение с других и выделяем кликнутый
            elif clicked_wid not in self.selected_widgets:
                self.clear_selected_widgets()
                self.add_and_select_widget(wid=clicked_wid)

            self.thumb_context_actions(menu=menu, wid=clicked_wid)

        menu.show_custom()

    def custom_mouseReleaseEvent(self, a0: QMouseEvent):

        if a0.button() != Qt.MouseButton.LeftButton:
            return

        clicked_wid = self.get_wid_under_mouse(a0=a0)

        if not isinstance(clicked_wid, Thumb):
            self.clear_selected_widgets()
            return
        
        if a0.modifiers() == Qt.KeyboardModifier.ShiftModifier:

            # шифт клик: если не было выделенных виджетов
            if not self.selected_widgets:

                self.add_and_select_widget(wid=clicked_wid)

            # шифт клик: если уже был выделен один / несколько виджетов
            else:

                coords = list(self.cell_to_wid)
                start_pos = (self.selected_widgets[-1].row, self.selected_widgets[-1].col)

                # шифт клик: слева направо (по возрастанию)
                if coords.index((clicked_wid.row, clicked_wid.col)) > coords.index(start_pos):
                    start = coords.index(start_pos)
                    end = coords.index((clicked_wid.row, clicked_wid.col))
                    coords = coords[start : end + 1]

                # шифт клик: справа налево (по убыванию)
                else:
                    start = coords.index((clicked_wid.row, clicked_wid.col))
                    end = coords.index(start_pos)
                    coords = coords[start : end]

                # выделяем виджеты по срезу координат coords
                for i in coords:

                    wid_ = self.cell_to_wid.get(i)

                    if wid_ not in self.selected_widgets:
                        self.add_and_select_widget(wid=wid_)

        elif a0.modifiers() == Qt.KeyboardModifier.ControlModifier:

            # комманд клик: был выделен виджет, снять выделение
            if clicked_wid in self.selected_widgets:
                self.selected_widgets.remove(clicked_wid)
                clicked_wid.set_no_frame()

            # комманд клик: виджет не был виделен, выделить
            else:
                self.add_and_select_widget(wid=clicked_wid)

        else:

            self.clear_selected_widgets()
            self.add_and_select_widget(wid=clicked_wid)
            # self.select_one_wid(wid=clicked_wid)

    def mouseDoubleClickEvent(self, a0):
        clicked_wid = self.get_wid_under_mouse(a0=a0)

        if clicked_wid:
            self.view_thumb_cmd(wid=clicked_wid)

    def mousePressEvent(self, a0):
        if a0.button() != Qt.MouseButton.LeftButton:
            return

        self.drag_start_position = a0.pos()
        return super().mousePressEvent(a0)
    
    def mouseMoveEvent(self, a0):

        distance = (a0.pos() - self.drag_start_position).manhattanLength()

        if distance < QApplication.startDragDistance():
            return
        
        wid = self.get_wid_under_mouse(a0=a0)

        if wid is None:
            return

        if wid and wid not in self.selected_widgets:
            self.clear_selected_widgets()
            self.add_and_select_widget(wid=wid)

        urls = [
            i.src
            for i in self.selected_widgets
        ]

        self.drag = QDrag(self)
        self.mime_data = QMimeData()
        img_ = QPixmap(Static.FILE_SVG).scaled(60, 60)
        self.drag.setPixmap(img_)
        
        urls = [
            QUrl.fromLocalFile(i)
            for i in urls
            ]

        self.mime_data.setUrls(urls)

        self.drag.setMimeData(self.mime_data)
        self.drag.exec_(Qt.DropAction.CopyAction)

        return super().mouseMoveEvent(a0)