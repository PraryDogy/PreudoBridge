import os
import subprocess

import sqlalchemy
from PyQt5.QtCore import QMimeData, QObject, Qt, QTimer, QUrl, pyqtSignal
from PyQt5.QtGui import (QContextMenuEvent, QDrag, QKeyEvent, QMouseEvent,
                         QPixmap)
from PyQt5.QtWidgets import (QAction, QApplication, QFrame, QGridLayout,
                             QLabel, QScrollArea, QSplitter, QVBoxLayout,
                             QWidget)
from sqlalchemy.exc import IntegrityError, OperationalError

from cfg import Dynamic, JsonData, Static, ThumbData
from database import CACHE, Dbase, OrderItem
from utils import URunnable, UThreadPool, Utils

from ._base_widgets import UMenu, USvgSqareWidget
from .actions import (ChangeViewMenu, CopyPath, FavAdd, FavRemove, Info,
                      OpenInApp, RatingMenu, RevealInFinder, SortMenu, TagMenu,
                      View)
from .win_copy_files import ErrorWin, WinCopyFiles
from .win_info import WinInfo
from .win_remove_files import WinRemoveFiles

SELECTED = "selected"
FONT_SIZE = "font-size: 11px;"
RAD = "border-radius: 4px"
IMG_WID_ATTR = "img_wid_attr"
SQL_ERRORS = (OperationalError, IntegrityError)
WID_UNDER_MOUSE = "win_under_mouse"
GRID_SPACING = 5
COL_COUNT = "col_count"
SHOW_IN_FOLDER = "Показать в папке"
UPDATE_GRID_T = "Обновить"
COPY_FILES_T = "Копировать"
PASTE_FILES_T = "Вставить объекты"
REMOVE_FILES_T = "Удалить"

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
    6: Static.DEINED_SYM + " " + Static.TAGS_DEINED,
    7: Static.REVIEW_SYM + " " + Static.TAGS_REVIEW,
    8: Static.APPROVED_SYM + " " + Static.TAGS_APPROWED,
    9: "",

    60: Static.DEINED_SYM + " " + Static.TAGS_DEINED,
    61: Static.DEINED_SYM + " " + Static.STAR_SYM,
    62: Static.DEINED_SYM + " " + Static.STAR_SYM * 2,
    63: Static.DEINED_SYM + " " + Static.STAR_SYM * 3,
    64: Static.DEINED_SYM + " " + Static.STAR_SYM * 4,
    65: Static.DEINED_SYM + " " + Static.STAR_SYM * 5,

    70: Static.REVIEW_SYM + " " + Static.TAGS_REVIEW,
    71: Static.REVIEW_SYM + " " + Static.STAR_SYM,
    72: Static.REVIEW_SYM + " " + Static.STAR_SYM * 2,
    73: Static.REVIEW_SYM + " " + Static.STAR_SYM * 3,
    74: Static.REVIEW_SYM + " " + Static.STAR_SYM * 4,
    75: Static.REVIEW_SYM + " " + Static.STAR_SYM * 5,

    80: Static.APPROVED_SYM + " " + Static.TAGS_APPROWED,
    81: Static.APPROVED_SYM + " " + Static.STAR_SYM,
    82: Static.APPROVED_SYM + " " + Static.STAR_SYM * 2,
    83: Static.APPROVED_SYM + " " + Static.STAR_SYM * 3,
    84: Static.APPROVED_SYM + " " + Static.STAR_SYM * 4,
    85: Static.APPROVED_SYM + " " + Static.STAR_SYM * 5,

}


class WorkerSignals(QObject):
    finished_ = pyqtSignal()


class SetDbRating(URunnable):
    def __init__(self, main_dir: str, order_item: OrderItem, new_rating: int):
        super().__init__()
        self.order_item = order_item
        self.new_rating = new_rating
        self.main_dir = main_dir
        self.signals_ = WorkerSignals()

    @URunnable.set_running_state
    def run(self):        
        db = os.path.join(self.main_dir, Static.DB_FILENAME)
        dbase = Dbase()
        engine = dbase.create_engine(path=db)
        if engine is None:
            return

        conn = engine.connect()
        hash_filename = Utils.get_hash_filename(self.order_item.name)
        stmt = sqlalchemy.update(CACHE)
        stmt = stmt.where(CACHE.c.name==hash_filename)
        stmt = stmt.values(rating=self.new_rating)

        try:
            conn.execute(stmt)
            conn.commit()
            self.signals_.finished_.emit()

        except SQL_ERRORS as e:
            conn.rollback()
            Utils.print_error(self, e)

        conn.close()


class ImgFrame(QFrame):
    def __init__(self):
        super().__init__()

    # def mouseReleaseEvent(self, a0):
    #     return super().mouseReleaseEvent(a0)
    
    # def mousePressEvent(self, a0):
    #     return super().mousePressEvent(a0)

    # def mouseMoveEvent(self, a0):
    #     return super().mouseMoveEvent(a0)
    
    # def mouseDoubleClickEvent(self, a0):
    #     return super().mouseDoubleClickEvent(a0)
    
    # def contextMenuEvent(self, a0):
    #     return super().contextMenuEvent(a0)


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

    # def mouseReleaseEvent(self, a0):
    #     return super().mouseReleaseEvent(a0)
    
    # def mousePressEvent(self, a0):
    #     return super().mousePressEvent(a0)

    # def mouseMoveEvent(self, a0):
    #     return super().mouseMoveEvent(a0)
    
    # def mouseDoubleClickEvent(self, a0):
    #     return super().mouseDoubleClickEvent(a0)
    
    # def contextMenuEvent(self, a0):
    #     return super().contextMenuEvent(a0)


class RatingWid(QLabel):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(FONT_SIZE)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_text(self, wid: OrderItem):
        text = RATINGS[wid.rating].strip()
        self.setText(text)

    # def mouseReleaseEvent(self, a0):
    #     return super().mouseReleaseEvent(a0)
    
    # def mousePressEvent(self, a0):
    #     return super().mousePressEvent(a0)

    # def mouseMoveEvent(self, a0):
    #     return super().mouseMoveEvent(a0)
    
    # def mouseDoubleClickEvent(self, a0):
    #     return super().mouseDoubleClickEvent(a0)
    
    # def contextMenuEvent(self, a0):
    #     return super().contextMenuEvent(a0)


class Thumb(OrderItem, QFrame):
    # Сигнал нужен, чтобы менялся заголовок в просмотрщике изображений
    # При изменении рейтинга или меток
    text_changed = pyqtSignal()
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

        if self.type_:
            svg_filename = self.type_.replace(".", "") + ".svg"
            svg_path = Dynamic.GENERIC_ICONS.get(svg_filename)

            if svg_path:
                self.svg_path = svg_path

            else:
                svg_path = Utils.create_generic(file_extension=self.type_)
                self.svg_path = svg_path

        else:
            self.svg_path = Static.FILE_SVG

        self.img_wid = USvgSqareWidget(src=self.svg_path, size=self.pixmap_size)
        self.img_frame_lay.addWidget(self.img_wid)

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
        self.img_wid.deleteLater()

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
            self.img_wid.setFixedSize(
                Thumb.pixmap_size,
                Thumb.pixmap_size
            )

    def set_green_text(self):
        self.text_wid.setStyleSheet(
            f"""
                background: transparent;
                {FONT_SIZE};
                {RAD};
                padding: 2px;
                color: green;
            """
        )

    def set_frame(self):

        self.text_wid.setStyleSheet(
            f"""
                background: {Static.BLUE_GLOBAL};
                {FONT_SIZE};
                {RAD};
                padding: 2px;
            """
        )

        self.img_frame.setStyleSheet(
            f"""
                background: {Static.GRAY_GLOBAL};
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

    def set_db_rating(self, rating: int):
        # устанавливается значение из бд
        self.rating = rating
        self.rating_wid.set_text(wid=self)
        self.text_changed.emit()

    def calculate_new_rating(self, new_rating: int):
        if new_rating > 5:
            rating = self.rating % 10
            tag = new_rating
        else:
            tag = self.rating // 10
            rating = new_rating
        return tag * 10 + rating


class ThumbFolder(Thumb):
    def __init__(self, src: str, size: int, mod: int, rating: int):
        super().__init__(src, size, mod, rating)

        self.svg_path = Static.FOLDER_SVG
        img_wid = self.img_frame.findChild(USvgSqareWidget)
        img_wid.load(self.svg_path)


class ThumbSearch(Thumb):
    load_st_grid_sig = pyqtSignal(tuple)

    def __init__(self, src: str, size: int, mod: int, rating: int):
        super().__init__(src, size, mod, rating)

    def show_in_folder_cmd(self):
        root = os.path.dirname(self.src)
        self.load_st_grid_sig.emit((root, self.src))


class Grid(QScrollArea):
    # сигналы должны быть идентичны list file system.py > ListFileSystem
    new_history_item = pyqtSignal(str)
    fav_cmd_sig = pyqtSignal(tuple)
    load_st_grid_sig = pyqtSignal(tuple)
    bar_bottom_update = pyqtSignal(tuple)
    move_slider_sig = pyqtSignal(int)
    change_view_sig = pyqtSignal(int)

    def __init__(self, main_dir: str, view_index: int, path_for_select: str):
        super().__init__()

        self.setAcceptDrops(True)
        self.setWidgetResizable(True)
        self.horizontalScrollBar().setDisabled(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.main_dir = main_dir
        self.view_index = view_index
        self.path_for_select = path_for_select
        self.path_to_wid: dict[str, Thumb] = {}
        self.selected_widgets: list[Thumb] = []
        self.cell_to_wid: dict[tuple, Thumb] = {}
        self.ordered_widgets: list[Thumb] = []

        self.main_wid = QWidget()
        self.setWidget(self.main_wid)

        flags = Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(GRID_SPACING)
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

    def get_col_count(self):
        main_win = self.window()

        win_ww = main_win.width()
        splitter = main_win.findChild(QSplitter)
        if splitter:
            left_menu: QWidget = splitter.children()[1]
            left_menu_ww = left_menu.width()
            return (win_ww - left_menu_ww) // Thumb.thumb_w
        else:
            print("no splitter")
            return 1

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
        cmd_ = lambda: self.bar_bottom_update.emit((src, None))
        QTimer.singleShot(100, cmd_)
    
    def order_(self):

        self.ordered_widgets = OrderItem.sort_items(self.ordered_widgets)
        
        Thumb.all = {
            wid.src: wid
            for wid in self.ordered_widgets
            if isinstance(wid, Thumb)
            }
        
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

    def resize_(self):
        wid_src_list = []

        for i in self.selected_widgets:
            wid_src_list.append(i.src)

        Thumb.calculate_size()
        for wid in self.ordered_widgets:
            wid.setup()

        for src, wid in self.path_to_wid.items():
            if src in wid_src_list:
                wid.set_frame()

    def rearrange(self):
        col_count = self.get_col_count()
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

        self.path_to_wid = {
            wid.src: wid
            for coords, wid in self.cell_to_wid.items()
        }

        if isinstance(self.path_for_select, str):
            wid = self.path_to_wid.get(self.path_for_select)
            self.select_one_wid(wid=wid)
            QTimer.singleShot(500, lambda: self.ensureWidgetVisible(wid))

        elif isinstance(self.path_for_select, (tuple, list)):
            widgets = [
                self.path_to_wid.get(i)
                for i in self.path_for_select
            ]

            for i in widgets:

                try:
                    i.set_frame()
                    self.selected_widgets.append(i)
                except AttributeError:
                    continue

            if widgets:
                QTimer.singleShot(500, lambda: self.ensureWidgetVisible(widgets[0]))
        
        return col_count


    def add_widget_data(self, wid: Thumb, row: int, col: int):
        wid.row, wid.col = row, col
        self.cell_to_wid[row, col] = wid
        self.path_to_wid[wid.src] = wid
        self.ordered_widgets.append(wid)

    def view_thumb_cmd(self, wid: OrderItem):

        if wid is None:
            return

        elif wid.type_ == Static.FOLDER_TYPE:
            self.mouseReleaseEvent = None
            self.new_history_item.emit(wid.src)
            self.load_st_grid_sig.emit((wid.src, None))

        elif wid.type_ in Static.IMG_EXT:
            from .win_img_view import WinImgView
            self.win_img_view = WinImgView(wid.src, self.path_to_wid)
            self.win_img_view.move_to_wid_sig.connect(self.select_one_wid)
            self.win_img_view.center(self.window())
            self.win_img_view.show()

        else:
            subprocess.Popen(["open", wid.src])

    def fav_cmd(self, offset: int, src: str):
        if 0 + offset == 1:
            self.fav_cmd_sig.emit(("add", src))
        else:
            self.fav_cmd_sig.emit(("del", src))

    def win_info_cmd(self, src: str):
        self.win_info = WinInfo(src)
        self.win_info.center(self.window())
        self.win_info.show()

    def thumb_context_actions(self, menu: UMenu, wid: Thumb):

        urls = [
            i.src
            for i in self.selected_widgets
        ]

        self.set_bottom_path(src=wid.src)

        view_action = View(menu)
        view_action.triggered.connect(lambda: self.view_thumb_cmd(wid))
        menu.addAction(view_action)

        if wid.type_ != Static.FOLDER_TYPE:
            open_menu = OpenInApp(menu, wid.src)
            menu.addMenu(open_menu)

        menu.addSeparator()

        info = Info(menu)
        info.triggered.connect(lambda: self.win_info_cmd(wid.src))
        menu.addAction(info)

        show_in_finder_action = RevealInFinder(menu, urls)
        menu.addAction(show_in_finder_action)

        copy_path = CopyPath(menu, urls)
        menu.addAction(copy_path)

        copy_files = QAction(f"{COPY_FILES_T} ({len(urls)})", menu)
        copy_files.triggered.connect(self.copy_files)
        menu.addAction(copy_files)

        menu.addSeparator()

        if wid.type_ == Static.FOLDER_TYPE:

            if wid.src in JsonData.favs:
                cmd_ = lambda: self.fav_cmd(offset=-1, src=wid.src)
                fav_action = FavRemove(menu)
                fav_action.triggered.connect(cmd_)
                menu.addAction(fav_action)

            else:
                cmd_ = lambda: self.fav_cmd(offset=1, src=wid.src)
                fav_action = FavAdd(menu)
                fav_action.triggered.connect(cmd_)
                menu.addAction(fav_action)

            menu.addSeparator()

        if wid.type_ in (*Static.IMG_EXT, Static.FOLDER_TYPE):
            rating_menu = RatingMenu(parent=menu, urls=urls, current_rating=wid.rating)
            rating_menu.new_rating.connect(self.set_new_rating)
            menu.addMenu(rating_menu)

            tags_menu = TagMenu(parent=menu, urls=urls, rating=wid.rating)
            tags_menu.new_tag.connect(self.set_new_rating)
            menu.addMenu(tags_menu)

            menu.addSeparator()

        if isinstance(wid, ThumbSearch):

            show_in_folder = QAction(SHOW_IN_FOLDER, menu)
            show_in_folder.triggered.connect(wid.show_in_folder_cmd)
            menu.addAction(show_in_folder)

            menu.addSeparator()

        menu.addSeparator()

        remove_files = QAction(REMOVE_FILES_T, menu)
        remove_files.triggered.connect(lambda: self.remove_files_cmd(urls))
        menu.addAction(remove_files)

    def grid_context_actions(self, menu: UMenu):

        self.set_bottom_path(src=self.main_dir)

        info = Info(menu)
        info.triggered.connect(lambda: self.win_info_cmd(self.main_dir))
        menu.addAction(info)

        reveal = RevealInFinder(menu, self.main_dir)
        menu.addAction(reveal)

        copy_ = CopyPath(parent=menu, src=self.main_dir)
        menu.addAction(copy_)

        menu.addSeparator()

        if self.main_dir in JsonData.favs:
            cmd_ = lambda: self.fav_cmd(offset=-1, src=self.main_dir)
            fav_action = FavRemove(menu)
            fav_action.triggered.connect(cmd_)
            menu.addAction(fav_action)

        else:
            cmd_ = lambda: self.fav_cmd(offset=+1, src=self.main_dir)
            fav_action = FavAdd(menu)
            fav_action.triggered.connect(cmd_)
            menu.addAction(fav_action)

        menu.addSeparator()

        change_view = ChangeViewMenu(menu, self.view_index)
        change_view.change_view_sig.connect(self.change_view_sig.emit)
        menu.addMenu(change_view)

        sort_menu = SortMenu(parent=menu)
        sort_menu.bar_bottom_update.connect(self.bar_bottom_update.emit)
        sort_menu.order_grid_sig.connect(self.order_)
        sort_menu.rearrange_grid_sig.connect(self.rearrange)
        menu.addMenu(sort_menu)

        menu.addSeparator()

        if Dynamic.files_to_copy:
            paste_files = QAction(PASTE_FILES_T, menu)
            paste_files.triggered.connect(self.paste_files)
            menu.addAction(paste_files)

        upd_ = QAction(UPDATE_GRID_T, menu)
        upd_.triggered.connect(lambda: self.load_st_grid_sig.emit((None, None)))
        menu.addAction(upd_)

        # col_count это аттрибут GridSearch
        # переназначаем действие QAction upd_ - обновить сетку, загрузив ее заново,
        # на order_, чтобы сетка не перезагружалась, а происходила сортировка
        # без перезагрузки
        if hasattr(self, COL_COUNT):
            upd_.disconnect()
            upd_.triggered.connect(self.order_)
            upd_.triggered.connect(self.rearrange)

    def set_new_rating(self, new_rating: int):
        # устанавливает рейтинг для выделенных в сетке виджетов
        for wid in self.selected_widgets:
            if wid.type_ in (*Static.IMG_EXT, Static.FOLDER_TYPE):
                if new_rating > 5:
                    rating = wid.rating % 10
                    tag = new_rating
                else:
                    tag = wid.rating // 10
                    rating = new_rating
                new_rating = tag * 10 + rating
                self.task_ = SetDbRating(self.main_dir, wid, new_rating)
                cmd_ = lambda w=wid: self.set_new_rating_fin(w, new_rating)
                self.task_.signals_.finished_.connect(cmd_)
                UThreadPool.start(self.task_)

    def set_new_rating_fin(self, wid: Thumb, new_rating: int):
        wid.rating = new_rating
        wid.rating_wid.set_text(wid=wid)
        wid.text_changed.emit()

    def get_wid_under_mouse(self, a0: QMouseEvent) -> None | Thumb:
        wid = QApplication.widgetAt(a0.globalPos())

        if isinstance(wid, (TextWidget, RatingWid, ImgFrame)):
            return wid.parent()
        elif isinstance(wid, (QLabel, USvgSqareWidget)):
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
        main_dir_ = Utils.add_system_volume(self.main_dir)
        for i in Dynamic.files_to_copy:
            # Если путь начинается с /Users/Username, то делаем абсолютный путь
            # /Volumes/Macintosh HD/Users/Username
            i = Utils.normalize_slash(i)
            i = Utils.add_system_volume(i)
            if os.path.commonpath([i, main_dir_]) == main_dir_:
                print("Нельзя копировать в себя")
                return

        if Dynamic.files_to_copy:
            self.win_copy = WinCopyFiles(self.main_dir)
            self.win_copy.load_st_grid_sig.connect(self.load_st_grid_sig.emit)
            self.win_copy.error_win_sig.connect(self.error_win_cmd)
            self.win_copy.center(self.window())
            self.win_copy.show()

    def error_win_cmd(self):
        self.win_copy.close()
        self.error_win = ErrorWin()
        self.error_win.center(self.window())
        self.error_win.show()

    def remove_files_cmd(self, urls: list[str]):
        self.rem_win = WinRemoveFiles(self.main_dir, urls)
        self.rem_win.load_st_grid_sig.connect(self.load_st_grid_sig.emit)
        self.rem_win.center(self.window())
        self.rem_win.show()

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        clicked_wid: Thumb | ThumbFolder 

        if a0.modifiers() & Qt.KeyboardModifier.ControlModifier:

            if a0.key() == Qt.Key.Key_V:
                self.paste_files()

            elif a0.key() == Qt.Key.Key_C:
                self.copy_files()

            if a0.key() == Qt.Key.Key_Up:

                old_root = self.main_dir
                root = os.path.dirname(self.main_dir)

                if root != os.sep:
                    self.new_history_item.emit(root)
                    self.load_st_grid_sig.emit((root, old_root))

            elif a0.key() == Qt.Key.Key_Down:
                if self.selected_widgets:
                    clicked_wid = self.selected_widgets[-1]
                    if clicked_wid:
                        self.select_one_wid(wid=clicked_wid)
                        self.view_thumb_cmd(clicked_wid)

            elif a0.key() == Qt.Key.Key_I:
                clicked_wid = self.selected_widgets[-1]
                if clicked_wid:
                    self.select_one_wid(wid=clicked_wid)
                    self.win_info_cmd(clicked_wid.src)
                else:
                    self.win_info_cmd(self.main_dir)

            elif a0.key() == Qt.Key.Key_Equal:
                new_value = Dynamic.pixmap_size_ind + 1
                if new_value <= len(ThumbData.PIXMAP_SIZE) - 1:
                    self.move_slider_sig.emit(new_value)

            elif a0.key() == Qt.Key.Key_Minus:
                new_value = Dynamic.pixmap_size_ind - 1
                if new_value >= 0:
                    self.move_slider_sig.emit(new_value)

            elif a0.key() == Qt.Key.Key_A:
                self.clear_selected_widgets()
                for cell, clicked_wid in self.cell_to_wid.items():
                    clicked_wid.set_frame()
                    self.selected_widgets.append(clicked_wid)

            elif a0.key() == Qt.Key.Key_Backspace:
                urls = [i.src for i in self.selected_widgets]
                self.remove_files_cmd(urls)

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
            self.set_new_rating(rating)
        
        return super().keyPressEvent(a0)

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:

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
            self.set_bottom_path(src=self.main_dir)
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
                self.set_bottom_path(src=clicked_wid.src)

        else:

            self.clear_selected_widgets()
            self.add_and_select_widget(wid=clicked_wid)
            self.select_one_wid(wid=clicked_wid)

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

        try:
            distance = (a0.pos() - self.drag_start_position).manhattanLength()
        except AttributeError:
            return

        if distance < QApplication.startDragDistance():
            return
        
        wid = self.get_wid_under_mouse(a0=a0)

        if wid is None:
            return

        if wid not in self.selected_widgets:
            self.clear_selected_widgets()
            self.add_and_select_widget(wid=wid)

        urls = [
            i.src
            for i in self.selected_widgets
        ]

        self.drag = QDrag(self)
        self.mime_data = QMimeData()

        if isinstance(wid.img_wid, USvgSqareWidget):
            USvgSqareWidget

        img_ = QPixmap(Static.COPY_FILES_PNG)
        self.drag.setPixmap(img_)
        
        urls = [
            QUrl.fromLocalFile(i)
            for i in urls
            ]

        if urls:
            self.mime_data.setUrls(urls)
            self.set_bottom_path(wid.src)

        self.drag.setMimeData(self.mime_data)
        self.drag.exec_(Qt.DropAction.CopyAction)

        return super().mouseMoveEvent(a0)
    