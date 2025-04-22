import os
import subprocess
from time import sleep

import sqlalchemy
from PyQt5.QtCore import QMimeData, QObject, Qt, QTimer, QUrl, pyqtSignal
from PyQt5.QtGui import (QContextMenuEvent, QDrag, QKeyEvent, QMouseEvent,
                         QPixmap)
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import (QAction, QApplication, QFrame, QGridLayout,
                             QLabel, QSplitter, QVBoxLayout, QWidget)
from sqlalchemy.exc import IntegrityError, OperationalError

from cfg import Dynamic, JsonData, Static, ThumbData
from database import CACHE, Dbase
from utils import URunnable, UThreadPool, Utils

from ._base_items import BaseItem, UMenu, UScrollArea
from .actions import (ChangeViewMenu, CopyPath, FavAdd, FavRemove, Info,
                      OpenInApp, OpenInNewWindow, RatingMenu, RevealInFinder,
                      SortMenu, View)
from .copy_files_win import CopyFilesWin, ErrorWin
from .info_win import InfoWin
from .remove_files_win import RemoveFilesWin

SELECTED = "selected"
FONT_SIZE = "font-size: 11px;"
RAD = "border-radius: 4px"
SQL_ERRORS = (OperationalError, IntegrityError)
WID_UNDER_MOUSE = "win_under_mouse"
GRID_SPACING = 5
SHOW_IN_FOLDER = "Показать в папке"
UPDATE_GRID_T = "Обновить"
COPY_FILES_T = "Скопировать объекты"
PASTE_FILES_T = "Вставить объекты"
REMOVE_FILES_T = "Удалить"
SLEEP_VALUE = 1

KEY_RATING = {
    Qt.Key.Key_0: 0,
    Qt.Key.Key_1: 1,
    Qt.Key.Key_2: 2,
    Qt.Key.Key_3: 3,
    Qt.Key.Key_4: 4,
    Qt.Key.Key_5: 5,
}

KEY_NAVI = {
    Qt.Key.Key_Left: (0, -1),
    Qt.Key.Key_Right: (0, 1),
    Qt.Key.Key_Up: (-1, 0),
    Qt.Key.Key_Down: (1, 0)
}

RATINGS = {
    0: "",
    1: Static.STAR_SYM,
    2: Static.STAR_SYM * 2,
    3: Static.STAR_SYM * 3,
    4: Static.STAR_SYM * 4,
    5: Static.STAR_SYM * 5,
}


class WorkerSignals(QObject):
    finished_ = pyqtSignal()


class SetDbRating(URunnable):
    def __init__(self, main_dir: str, base_item: BaseItem, new_rating: int):
        super().__init__()
        self.base_item = base_item
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
        hash_filename = Utils.get_hash_filename(self.base_item.name)
        stmt = sqlalchemy.update(CACHE)
        stmt = stmt.where(CACHE.c.name==hash_filename)
        stmt = stmt.values(rating=self.new_rating)
        Dbase.commit_(conn, stmt)
        self.signals_.finished_.emit()
        conn.close()


class ImgFrame(QFrame):
    def __init__(self):
        super().__init__()


class TextWidget(QLabel):
    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(FONT_SIZE)

    def set_text(self, name: str) -> list[str]:
        name: str | list = name
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

    def set_text(self, rating: int):
        try:
            text = RATINGS.get(rating).strip()
            self.setText(text)
        except Exception as e:
            print(rating, e)


class Thumb(BaseItem, QFrame):
    # Сигнал нужен, чтобы менялся заголовок в просмотрщике изображений
    # При изменении рейтинга или меток
    text_changed = pyqtSignal()
    pixmap_size = 0
    thumb_w = 0
    thumb_h = 0
    img_obj_name = "img_frame"
    text_obj_name = "text_frame_"

    def __init__(self, src: str, rating: int = 0):
        """
        Обязательно задать параметры:   
        setup_attrs, setup_child_widgets, set_no_frame 
        """
        QFrame.__init__(self, parent=None)
        BaseItem.__init__(self, src, rating)

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
        self.img_frame.setObjectName(Thumb.img_obj_name)
        self.v_lay.addWidget(self.img_frame, alignment=Qt.AlignmentFlag.AlignCenter)

        self.img_frame_lay = QVBoxLayout()
        self.img_frame_lay.setContentsMargins(0, 0, 0, 0)
        self.img_frame_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_frame.setLayout(self.img_frame_lay)

        self.img_wid = QSvgWidget()
        self.img_frame_lay.addWidget(self.img_wid)

        self.text_wid = TextWidget()
        self.text_wid.setObjectName(Thumb.text_obj_name)
        self.v_lay.addWidget(self.text_wid, alignment=Qt.AlignmentFlag.AlignCenter)

        self.rating_wid = RatingWid()
        self.v_lay.addWidget(self.rating_wid, alignment=Qt.AlignmentFlag.AlignCenter)

        # self.setStyleSheet("background: gray;")

    @classmethod
    def calculate_size(cls):
        ind = Dynamic.pixmap_size_ind
        cls.pixmap_size = ThumbData.PIXMAP_SIZE[ind]
        cls.img_frame_size = Thumb.pixmap_size + ThumbData.OFFSET
        cls.thumb_w = ThumbData.THUMB_W[ind]
        cls.thumb_h = ThumbData.THUMB_H[ind]

    def set_svg_icon(self, path: str):
        self.img_wid.load(path)
        self.img_wid.setFixedSize(Thumb.pixmap_size, Thumb.pixmap_size)

    def set_image(self, pixmap: QPixmap):
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

    def setup_child_widgets(self):
        """
        Устанавливает фиксированные размеры для дочерних виджетов Thumb     
        Устанавливает текст в дочерних виджетах в соответствии с размерами  
        Устанавливает изображение в дочерних виджетах в соответствии в размерами
        """
        self.text_wid.set_text(self.name)
        self.rating_wid.set_text(self.rating)

        self.setFixedSize(Thumb.thumb_w, Thumb.thumb_h)
        self.img_wid.setFixedSize(Thumb.pixmap_size, Thumb.pixmap_size)
        self.img_frame.setFixedSize(Thumb.img_frame_size, Thumb.img_frame_size)

        if self.get_pixmap_storage():
            pixmap =  Utils.pixmap_scale(self.get_pixmap_storage(), Thumb.pixmap_size)
            self.img_wid.setPixmap(pixmap)
            self.img_wid.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_green_text(self):
        self.setStyleSheet(
            f"""
            #{Thumb.text_obj_name} {{
                background: transparent;
                {FONT_SIZE};
                {RAD};
                padding: 2px;
                color: green;
            }}
            """
        )

    def set_frame(self):
        self.setStyleSheet(
            f"""
            #{Thumb.text_obj_name} {{
                background: {Static.BLUE_GLOBAL};
                {FONT_SIZE};
                {RAD};
                padding: 2px;
            }}
            #{Thumb.img_obj_name} {{
                background: {Static.GRAY_GLOBAL};
                {FONT_SIZE};
                {RAD};
            }}
            """
        )

    def set_no_frame(self):
        self.setStyleSheet(
            f"""
            #{Thumb.text_obj_name} {{
                background: transparent;
                {FONT_SIZE};
                {RAD};
                padding: 2px;
            }}
            #{Thumb.img_obj_name} {{
                background: transparent;
                {FONT_SIZE};
                {RAD};
            }}
            """
        )


class Grid(UScrollArea):
    urls_to_copy: list[str] = []

    def __init__(self, main_dir: str, view_index: int, url_for_select: str):
        super().__init__()
        self.setAcceptDrops(True)
        self.setWidgetResizable(True)
        self.horizontalScrollBar().setDisabled(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.is_grid_search: bool = False
        self.main_dir = main_dir
        self.view_index = view_index

        # для выделения виджета после формирования / перетасовки сетки
        self.url_for_select = url_for_select

        # url файла / папки - виджет
        self.url_to_wid: dict[str, Thumb] = {}

        # выделенные в сетке виджеты
        self.selected_widgets: list[Thumb] = []

        # (строка, столбец) - виджет
        self.cell_to_wid: dict[tuple, Thumb] = {}

        # виджеты с порядком сортировки
        self.sorted_widgets: list[Thumb] = []

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
        """
        Получает количество столбцов для сетки по формуле:  
        Ширина окна минус ширина левого виджета в сплиттере (левое меню)
        """
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
        """
        Очищает визуальное выделение с выделенных виджетов и очищает список.  
        Выделяет виджет, добавляет его в список выделенных виджетов.
        """
        if wid is None:
            return

        self.clear_selected_widgets()

        wid.set_frame()
        self.selected_widgets.append(wid)
        self.ensureWidgetVisible(wid)
        self.path_bar_update_cmd(wid.src)

    def path_bar_update_cmd(self, src: str):
        """
        Указывает новый путь для path_bar.py > PathBar.  
        Действие отложено по таймеру, т.к. без таймера действие может быть
        заблокировано например контекстным меню
        """
        cmd_ = lambda: self.path_bar_update.emit(src)
        QTimer.singleShot(100, cmd_)
    
    def sort_(self):
        """
        Сортирует виджеты по аттрибуту BaseItem / Thumb
        """
        self.sorted_widgets = BaseItem.sort_items(self.sorted_widgets)
                
    def filter_(self):
        """
        Скрывает виджеты, не соответствующие установленному фильтру.    
        Например, если фильтр установлен "отобразить 5 звезд",     
        то будут отображены только виджеты с рейтингом 5, остальные скрыты,     
        но не удалены.  
        Необходимо затем вызвать метод rearrange
        """
        for wid in self.sorted_widgets:
            show_widget = True
            if Dynamic.rating_filter > 0:
                if wid.rating != Dynamic.rating_filter:
                    show_widget = False
            if show_widget:
                wid.must_hidden = False
                wid.show()
            else:
                wid.must_hidden = True
                wid.hide()

    def resize_(self):
        """
        Изменяет размер виджетов Thumb. Подготавливает дочерние виджеты Thumb
        к новым размерам.   
        Необходимо затем вызвать метод rearrange
        """
        Thumb.calculate_size()
        for cell, wid in self.cell_to_wid.items():
            wid.setup_child_widgets()

    def rearrange(self):
        """
        Перетасовывает виджеты в сетке на основе новых условий.     
        Например был изменен размер виджета Thumb с 10x10 на 15x15,     
        соответственно число столбцов и строк в сетке виджетов Thumb    
        должно измениться, и для этого вызывается метод rearrange
        """
        col_count = self.get_col_count()

        # очищаем cell_to_wid, чтобы заполнить этот словарь новыми координатами
        self.cell_to_wid.clear()
        row, col = 0, 0

        # проходим циклом по отсортированным виджетам
        for wid in self.sorted_widgets:

            # соответствует методу filter_ (смотри метод filter_)
            if wid.must_hidden:
                continue

            self.grid_layout.addWidget(wid, row, col)

            # добавляем новые координаты в словарь
            self.cell_to_wid[row, col] = wid

            # меняем аттрибуты строки и столбца в виджете Thumb
            wid.row, wid.col = row, col

            col += 1
            if col >= col_count:
                col = 0
                row += 1

        # формируем новый словарь путь к файлу: виджет Thumb
        # на основе cell_to_wid, чтобы пропустить скрытые виджеты
        self.url_to_wid = {
            wid.src: wid
            for coords, wid in self.cell_to_wid.items()
        }

        # если в сетку был передан аттрибут url_for_select,
        # то после того, как сетка виджетов была сформирована,
        # будет выделен виджет, который ищется в url_to_wid
        if isinstance(self.url_for_select, str):
            wid = self.url_to_wid.get(self.url_for_select)
            self.select_one_wid(wid)
            QTimer.singleShot(500, lambda: self.ensureWidgetVisible(wid))

        # тоже самое, но будет выделено сразу несколько виджетов
        elif isinstance(self.url_for_select, (tuple, list)):
            widgets = [
                self.url_to_wid.get(i)
                for i in self.url_for_select
            ]
            for i in widgets:
                try:
                    i.set_frame()
                    self.selected_widgets.append(i)
                except AttributeError:
                    continue
            if widgets:
                cmd_ = lambda: self.ensureWidgetVisible(widgets[0])
                QTimer.singleShot(500, cmd_)
        
        return col_count

    def add_widget_data(self, wid: Thumb, row: int, col: int):
        """
        Добавляет данные о виджете в необходимые списки и словари,
        а так же устанавливает аттрибуты Thumb: row, col
        """
        wid.row, wid.col = row, col
        self.cell_to_wid[row, col] = wid
        self.url_to_wid[wid.src] = wid
        self.sorted_widgets.append(wid)

    def view_thumb_cmd(self, wid: BaseItem):
        """
        Просмотр виджета:
        - папка: откроется новая сетка виджетов соответствующая директории папки
        - изображение: откроется внутренний просмотрщик изображений
        - другие файлы: откроется программа по умолчанию
        """
        if wid is None:
            return

        elif wid.type_ == Static.FOLDER_TYPE:
            self.mouseReleaseEvent = None
            self.new_history_item.emit(wid.src)
            self.load_st_grid_sig.emit((wid.src, None))

        elif wid.type_ in Static.IMG_EXT:
            # избегаем ошибки кругового импорта
            from .img_view_win import ImgViewWin
            self.win_img_view = ImgViewWin(wid.src, self.url_to_wid)
            self.win_img_view.move_to_wid_sig.connect(lambda wid: self.select_one_wid(wid))
            self.win_img_view.new_rating.connect(lambda value: self.set_new_rating(value))
            self.win_img_view.center(self.window())
            self.win_img_view.show()

        else:
            subprocess.Popen(["open", wid.src])

    def fav_cmd(self, offset: int, src: str):
        """
        Добавляет / удаляет папку в меню избранного. Аргументы:
        - offset: -1 (удалить из избранного) или 1(добавить в избранное)
        - src: путь к папке
        """
        if 0 + offset == 1:
            self.fav_cmd_sig.emit(("add", src))
        else:
            self.fav_cmd_sig.emit(("del", src))

    def win_info_cmd(self, src: str):
        """
        Открыть окно информации о файле / папке
        """
        self.win_info = InfoWin(src)
        self.win_info.center(self.window())
        self.win_info.show()

    def thumb_context_actions(self, menu_: UMenu, wid: Thumb):
        """
        Контекстное меню Thumb
        """
        # собираем пути к файлам / папкам у выделенных виджетов
        urls = [i.src for i in self.selected_widgets]

        self.path_bar_update_cmd(wid.src)

        view_action = View(menu_)
        view_action.triggered.connect(lambda: self.view_thumb_cmd(wid))
        menu_.addAction(view_action)

        if wid.type_ != Static.FOLDER_TYPE:
            open_menu = OpenInApp(menu_, wid.src)
            menu_.addMenu(open_menu)
        else:
            new_window = OpenInNewWindow(menu_)
            cmd_ = lambda: self.open_in_new_window.emit(wid.src)
            new_window.triggered.connect(cmd_)
            menu_.addAction(new_window)

        menu_.addSeparator()

        info = Info(menu_)
        info.triggered.connect(lambda: self.win_info_cmd(wid.src))
        menu_.addAction(info)

        show_in_finder_action = RevealInFinder(menu_, urls)
        menu_.addAction(show_in_finder_action)

        copy_path = CopyPath(menu_, urls)
        menu_.addAction(copy_path)

        copy_files = QAction(f"{COPY_FILES_T} ({len(urls)})", menu_)
        copy_files.triggered.connect(self.setup_urls_to_copy)
        menu_.addAction(copy_files)

        menu_.addSeparator()

        if wid.type_ == Static.FOLDER_TYPE:
            if wid.src in JsonData.favs:
                cmd_ = lambda: self.fav_cmd(offset=-1, src=wid.src)
                fav_action = FavRemove(menu_)
                fav_action.triggered.connect(cmd_)
                menu_.addAction(fav_action)
            else:
                cmd_ = lambda: self.fav_cmd(offset=1, src=wid.src)
                fav_action = FavAdd(menu_)
                fav_action.triggered.connect(cmd_)
                menu_.addAction(fav_action)

            menu_.addSeparator()

        if wid.type_ in (*Static.IMG_EXT, Static.FOLDER_TYPE):
            rating_menu = RatingMenu(parent=menu_, urls=urls, current_rating=wid.rating)
            rating_menu.new_rating.connect(self.set_new_rating)
            menu_.addMenu(rating_menu)

            menu_.addSeparator()

        # is grid search устанавливается на True при инициации GridSearch
        if self.is_grid_search:
            show_in_folder = QAction(SHOW_IN_FOLDER, menu_)
            cmd_ = lambda: self.show_in_folder_cmd(wid)
            show_in_folder.triggered.connect(cmd_)
            menu_.addAction(show_in_folder)
            menu_.addSeparator()

        menu_.addSeparator()

        remove_files = QAction(REMOVE_FILES_T, menu_)
        remove_files.triggered.connect(lambda: self.remove_files_cmd(urls))
        menu_.addAction(remove_files)

    def show_in_folder_cmd(self, wid: Thumb):
        """
        В сетке GridSearch к каждому Thumb добавляется пункт "Показать в папке"     
        Загружает сетку GridStandart с указанным путем к файлу / папке
        """
        new_main_dir = os.path.dirname(wid.src)
        self.load_st_grid_sig.emit((new_main_dir, wid.src))

    def setup_urls_to_copy(self):
        """
        Очищает список путей к файлам / папкам для последующего копирования.    
        Формирует новый список на основе списка выделенных виджетов Thumb
        """
        Grid.urls_to_copy.clear()
        for i in self.selected_widgets:
            Grid.urls_to_copy.append(i.src)

    def paste_files(self):
        """
        Вставляет файлы на основе списка Grid.urls_to_copy в текущую директорию.    
        Открывает окно копирования файлов.  
        Запускает QRunnable для копирования файлов. Испускает сигналы:
        - error win sig при ошибке копирования, откроется окно ошибки
        - finished_ добавит в сетку новые Thumb
        
        Предотвращает вставку в саму себя.  
        Например нельзя скопировать Downloads в Downloads.
        """
        self.win_copy = CopyFilesWin(self.main_dir, Grid.urls_to_copy)
        self.win_copy.finished_.connect(lambda urls: self.paste_files_fin(urls))
        self.win_copy.error_win_sig.connect(self.error_win_cmd)
        self.win_copy.center(self.window())
        self.win_copy.show()

    def paste_files_fin(self, urls: list[str]):
        """
        Заменяет существующие виджеты сетки новыми, если совпадают url.    
        Добавляет новые виджеты в сетку.    
        Сортирует сетку, перетасовывает сетку.   
        Испускет сигнал принудительной загрузки изображений для скопированных виджетов.
        """
        for dir in urls:
            # если url есть в списке path to wid, то удаляем информацию о виджете
            # и сам виджет из сетки
            if dir in self.url_to_wid:
                wid = self.remove_widget_data(dir)
                if wid:
                    wid.deleteLater()
            # инициируем новый виджет
            wid = Thumb(dir)
            wid.setup_attrs()
            wid.setup_child_widgets()
            wid.set_no_frame()
            wid.set_svg_icon(Utils.get_generic_icon_path(wid.type_))
            # ищем последнюю строку и столбец в cell to wid
            # прибавляем +1 к строке и столбец:
            # сколько прибавлять неважно, так как при перетасовке установится
            # правильное значение строки и столбца
            row, col = list(self.cell_to_wid.keys())[-1]
            new_row, new_col = row + 1, col + 1
            self.add_widget_data(wid, new_row, new_col)
            self.grid_layout.addWidget(wid, new_row, new_col)
        self.sort_()
        self.rearrange()
        # испускает сигнал со списком Urls в MainWin, и MainWin
        # инициирует метод force_load_images_cmd в GridStandart,
        # чтобы прогрузить изображения для вставленных виджетов.
        self.force_load_images_sig.emit(urls)
        Grid.urls_to_copy.clear()

    def error_win_cmd(self):
        """
        Открывает окно ошибки копирования файлов
        """
        self.win_copy.close()
        self.error_win = ErrorWin()
        self.error_win.center(self.window())
        self.error_win.show()

    def remove_files_cmd(self, urls: list[str]):
        """
        Окно удаления выделенных виджетов, на основе которых формируется список     
        файлов для удаления.    
        Запускается apple script remove_files.scpt через subprocess через QRunnable,
        чтобы переместить файлы в корзину, а не удалять их безвозвратно.
        Окно испускет сигнал finished, что ведет к методу remove files fin
        """
        self.rem_win = RemoveFilesWin(self.main_dir, urls)
        self.rem_win.finished_.connect(lambda urls: self.remove_files_fin(urls))
        self.rem_win.center(self.window())
        self.rem_win.show()

    def remove_widget_data(self, dir: str) -> Thumb | None:
        """
        Удаляет данные о виджете из необходимых списков и словарей.     
        Порядок удаления важен. Не менять.  
        Возвращет найденный виджет на основе url или None
        """
        wid: Thumb = self.url_to_wid.get(dir)
        if wid:
            # удаляем виджет из сетки координат
            self.cell_to_wid.pop((wid.row, wid.col))
            # удаляем виджет из списка путей
            self.url_to_wid.pop(dir)
            # удаляем из сортированных виджетов
            self.sorted_widgets.remove(wid)
            return wid
        else:
            return None

    def remove_files_fin(self, urls: list[str]):
        """
        Удаляет виджеты и данные о виджетах на основе получанного списка url.   
        Снимает визуальное выделение с выделенных виджетов.     
        Очищает список выделенных вижетов.  
        Запускает перетасовку сетки.    
        """
        for i in urls:
            wid = self.remove_widget_data(i)
            if wid:
                wid.deleteLater()

        for i in self.selected_widgets:
            i.set_no_frame()
        self.selected_widgets.clear()
        self.rearrange()

    def grid_context_actions(self, menu_: UMenu):
        """
        Контекстное меню Grid
        """
        self.path_bar_update_cmd(self.main_dir)

        info = Info(menu_)
        info.triggered.connect(lambda: self.win_info_cmd(self.main_dir))
        menu_.addAction(info)

        reveal = RevealInFinder(menu_, self.main_dir)
        menu_.addAction(reveal)

        copy_ = CopyPath(menu_, self.main_dir)
        menu_.addAction(copy_)

        menu_.addSeparator()

        if self.main_dir in JsonData.favs:
            cmd_ = lambda: self.fav_cmd(-1, self.main_dir)
            fav_action = FavRemove(menu_)
            fav_action.triggered.connect(cmd_)
            menu_.addAction(fav_action)

        else:
            cmd_ = lambda: self.fav_cmd(+1, self.main_dir)
            fav_action = FavAdd(menu_)
            fav_action.triggered.connect(cmd_)
            menu_.addAction(fav_action)

        menu_.addSeparator()

        change_view = ChangeViewMenu(menu_, self.view_index)
        change_view.change_view_sig.connect(self.change_view_sig.emit)
        menu_.addMenu(change_view)

        sort_menu = SortMenu(menu_)
        sort_menu.sort_grid_sig.connect(self.sort_)
        sort_menu.rearrange_grid_sig.connect(self.rearrange)
        sort_menu.sort_bar_update_sig.connect(self.sort_bar_update.emit)
        menu_.addMenu(sort_menu)

        menu_.addSeparator()

        if Grid.urls_to_copy and not self.is_grid_search:
            paste_files = QAction(PASTE_FILES_T, menu_)
            paste_files.triggered.connect(self.paste_files)
            menu_.addAction(paste_files)

        upd_ = QAction(UPDATE_GRID_T, menu_)
        upd_.triggered.connect(lambda: self.load_st_grid_sig.emit((None, None)))
        menu_.addAction(upd_)

    def set_new_rating(self, new_rating: int):
        """
        Устанавливает рейтинг для выделенных в сетке виджетов:
        - Делается запись в базу данных через QRunnable
        - При успешной записи QRunnable испускает сигнал finished
        """
        for wid in self.selected_widgets:
            if wid.type_ in (*Static.IMG_EXT, Static.FOLDER_TYPE):
                self.task_ = SetDbRating(self.main_dir, wid, new_rating)
                cmd_ = lambda w=wid: self.set_new_rating_fin(w, new_rating)
                self.task_.signals_.finished_.connect(cmd_)
                UThreadPool.start(self.task_)

    def set_new_rating_fin(self, wid: Thumb, new_rating: int):
        """
        Устанавливает визуальный рейтинг и аттрибут рейтинга для Thumb при  
        успешной записи в базу данных
        """
        wid.rating = new_rating
        wid.rating_wid.set_text(new_rating)
        wid.text_changed.emit()

    def get_wid_under_mouse(self, a0: QMouseEvent) -> None | Thumb:
        """
        Получает виджет Thumb, по которому произошел клик.  
        Клик засчитывается, если он произошел по дочерним виджетам Thumb:   
        TextWidget, RatingWid, ImgFrame     
        QLabel и QSvgWidget являются дочерними виджетами ImgFrame, поэтому  
        в случае клика по ним, возвращается .parent().parent()
        """
        wid = QApplication.widgetAt(a0.globalPos())
        
        if isinstance(wid, (TextWidget, RatingWid, ImgFrame)):
            return wid.parent()
        elif isinstance(wid, (QLabel, QSvgWidget)):
            return wid.parent().parent()
        else:
            return None
        
    def clear_selected_widgets(self):
        """
        Очищает список выделенных виджетов и снимает визуальное выделение с них
        """
        for i in self.selected_widgets:
            i.set_no_frame()
        self.selected_widgets.clear()

    def select_widget(self, wid: Thumb):
        """
        Добавляет виджет в список выделенных виджетов и выделяет виджет визуально.  
        Метод похож на select_one_widget, но поддерживает выделение нескольких  
        виджетов.
        """
        if isinstance(wid, Thumb):
            self.selected_widgets.append(wid)
            wid.set_frame()

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        clicked_wid: Thumb

        if a0.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if a0.key() == Qt.Key.Key_C:
                self.setup_urls_to_copy()

            elif a0.key() == Qt.Key.Key_V:
                if not self.is_grid_search:
                    self.paste_files()

            elif a0.key() == Qt.Key.Key_Up:
                self.level_up.emit()

            elif a0.key() == Qt.Key.Key_Down:
                # если есть выделенные виджеты, то берется url последнего из списка
                if self.selected_widgets:
                    clicked_wid = self.selected_widgets[-1]
                    if clicked_wid:
                        self.select_one_wid(clicked_wid)
                        self.view_thumb_cmd(clicked_wid)

            elif a0.key() == Qt.Key.Key_I:
                clicked_wid = self.selected_widgets[-1]
                if clicked_wid:
                    self.select_one_wid(clicked_wid)
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
        menu_ = UMenu(parent=self)
        clicked_wid = self.get_wid_under_mouse(a0)

        # клик по пустому пространству
        if not clicked_wid:
            self.clear_selected_widgets()
            self.grid_context_actions(menu_)

        # клик по виджету
        else:
            # если не было выделено ни одного виджет ранее
            # то выделяем кликнутый
            if not self.selected_widgets:
                self.select_widget(clicked_wid)
            # если есть выделенные виджеты, но кликнутый виджет не выделены
            # то снимаем выделение с других и выделяем кликнутый
            elif clicked_wid not in self.selected_widgets:
                self.clear_selected_widgets()
                self.select_widget(clicked_wid)
            self.thumb_context_actions(menu_, clicked_wid)

        menu_.show_()

    def custom_mouseReleaseEvent(self, a0: QMouseEvent):
        if a0.button() != Qt.MouseButton.LeftButton:
            return

        clicked_wid = self.get_wid_under_mouse(a0)

        if not isinstance(clicked_wid, Thumb):
            self.clear_selected_widgets()
            self.path_bar_update_cmd(self.main_dir)
            return
        
        if a0.modifiers() == Qt.KeyboardModifier.ShiftModifier:
            # шифт клик: если не было выделенных виджетов
            if not self.selected_widgets:
                self.select_widget(clicked_wid)
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
                        self.select_widget(wid=wid_)

        elif a0.modifiers() == Qt.KeyboardModifier.ControlModifier:

            # комманд клик: был выделен виджет, снять выделение
            if clicked_wid in self.selected_widgets:
                self.selected_widgets.remove(clicked_wid)
                clicked_wid.set_no_frame()

            # комманд клик: виджет не был виделен, выделить
            else:
                self.select_widget(wid=clicked_wid)
                self.path_bar_update_cmd(clicked_wid.src)

        else:
            # self.clear_selected_widgets()
            # self.select_widget(clicked_wid)
            self.select_one_wid(clicked_wid)

    def mouseDoubleClickEvent(self, a0):
        clicked_wid = self.get_wid_under_mouse(a0=a0)
        if clicked_wid:
            self.view_thumb_cmd(clicked_wid)

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
        
        wid = self.get_wid_under_mouse(a0)

        if wid is None:
            return

        if wid not in self.selected_widgets:
            self.select_one_wid(wid)

        urls = [
            i.src
            for i in self.selected_widgets
        ]

        self.drag = QDrag(self)
        self.mime_data = QMimeData()

        img_ = QPixmap(Static.COPY_FILES_PNG)
        self.drag.setPixmap(img_)
        
        urls = [
            QUrl.fromLocalFile(i)
            for i in urls
            ]

        if urls:
            self.mime_data.setUrls(urls)
            self.path_bar_update_cmd(wid.src)

        self.drag.setMimeData(self.mime_data)
        self.drag.exec_(Qt.DropAction.CopyAction)

        return super().mouseMoveEvent(a0)
    
    def dragEnterEvent(self, a0):
        if self.is_grid_search:
            return
        if a0.mimeData().hasUrls():
            a0.acceptProposedAction()
        return super().dragEnterEvent(a0)
    
    def dropEvent(self, a0):
        Grid.urls_to_copy.clear()
        Grid.urls_to_copy = [i.toLocalFile() for i in a0.mimeData().urls()]

        main_dir_ = Utils.normalize_slash(self.main_dir)
        main_dir_ = Utils.add_system_volume(main_dir_)
        for i in Grid.urls_to_copy:
            i = Utils.normalize_slash(i)
            i = Utils.add_system_volume(i)
            if os.path.commonpath([i, main_dir_]) == main_dir_:
                print("Нельзя копировать в себя")
                return

        if Grid.urls_to_copy:
            self.paste_files()

        return super().dropEvent(a0)
