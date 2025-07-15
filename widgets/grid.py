import gc
import os
import subprocess

import sqlalchemy
from PyQt5.QtCore import (QMimeData, QObject, QPoint, QRect, QSize, Qt, QTimer,
                          QUrl, pyqtSignal)
from PyQt5.QtGui import (QContextMenuEvent, QDrag, QKeyEvent, QMouseEvent,
                         QPixmap)
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import (QApplication, QFrame, QGridLayout, QLabel,
                             QRubberBand, QSplitter, QVBoxLayout, QWidget)

from cfg import Dynamic, JsonData, Static, ThumbData
from database import CACHE, Dbase
from utils import Utils

from ._base_items import (BaseItem, MainWinItem, SortItem, UMenu, URunnable,
                          UScrollArea, UThreadPool)
from .actions import GridActions, ItemActions
from .copy_files_win import CopyFilesWin, ErrorWin
from .info_win import InfoWin
from .remove_files_win import RemoveFilesWin
from .rename_win import RenameWin

FONT_SIZE = 11
BORDER_RADIUS = 4

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

    def task(self):        
        db = os.path.join(self.main_dir, Static.DB_FILENAME)
        dbase = Dbase()
        engine = dbase.create_engine(path=db)
        if engine is None:
            return
        conn = Dbase.open_connection(engine)
        hash_filename = Utils.get_hash_filename(self.base_item.name)
        stmt = sqlalchemy.update(CACHE)
        stmt = stmt.where(CACHE.c.name==hash_filename)
        stmt = stmt.values(rating=self.new_rating)
        Dbase.execute_(conn, stmt)
        Dbase.commit_(conn)
        self.signals_.finished_.emit()
        Dbase.close_connection(conn)


class ImgFrame(QFrame):
    def __init__(self):
        super().__init__()


class TextWidget(QLabel):
    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(f"""font-size: {FONT_SIZE}px;""")

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
    text_mod = "Изм: "
    text_size = "Размер: "

    def __init__(self):
        super().__init__()
        self.blue_color = "#6199E4"
        self.setStyleSheet(
            f"""
            font-size: {FONT_SIZE}px;
            color: {self.blue_color};
            """
        )
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_text(self, thumb: "Thumb"):
        try:
            if thumb.rating > 0:
                mod_row = RATINGS.get(thumb.rating).strip()
            else:
                mod_row = self.text_mod + Utils.get_f_date(thumb.mod)
                if thumb.type_ == Static.FOLDER_TYPE:
                    sec_row = str("")
                else:
                    sec_row = self.text_size + Utils.get_f_size(thumb.size, 0)
                mod_row = "\n".join((mod_row, sec_row))
            self.setText(mod_row)
        except Exception as e:
            Utils.print_error(e)


class Thumb(BaseItem, QFrame):
    # Сигнал нужен, чтобы менялся заголовок в просмотрщике изображений
    # При изменении рейтинга или меток
    text_changed = pyqtSignal()
    pixmap_size = 0
    thumb_w = 0
    thumb_h = 0
    corner = 0
    img_obj_name = "img_frame"
    text_obj_name = "text_frame_"

    def __init__(self, src: str, rating: int = 0):
        """
        Обязательно задать параметры:   
        setup_attrs, setup_child_widgets, set_no_frame 
        """
        QFrame.__init__(self, parent=None)
        BaseItem.__init__(self, src, rating)

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
        cls.corner = ThumbData.CORNER[ind]

    def set_svg_icon(self):
        if self.src.count(os.sep) == 2:
            path = Static.HDD_SVG
        else:
            path = Utils.get_generic_icon_path(self.type_, Static.GENERIC_ICONS_DIR)

        self.img_wid.load(path)
        self.img_wid.setFixedSize(Thumb.pixmap_size, Thumb.pixmap_size)

    def set_image(self, pixmap: QPixmap):
        old_wid = self.img_wid

        self.img_wid = QLabel()
        self.img_wid.setPixmap(
            Utils.pixmap_scale(pixmap, Thumb.pixmap_size)
        )
        self.img_frame_lay.addWidget(
            self.img_wid,
            alignment=Qt.AlignmentFlag.AlignCenter
        )

        old_wid.setParent(None)
        old_wid.deleteLater()

    def setup_child_widgets(self):
        """
        Устанавливает фиксированные размеры для дочерних виджетов Thumb     
        Устанавливает текст в дочерних виджетах в соответствии с размерами  
        Устанавливает изображение в дочерних виджетах в соответствии в размерами
        """
        self.text_wid.set_text(self.name)
        self.rating_wid.set_text(self)

        self.setFixedSize(Thumb.thumb_w, Thumb.thumb_h)
        self.img_wid.setFixedSize(Thumb.pixmap_size, Thumb.pixmap_size)
        self.img_frame.setFixedSize(Thumb.img_frame_size, Thumb.img_frame_size)

        pixmap_ = self.get_pixmap_storage()
        if pixmap_:
            pixmap =  Utils.pixmap_scale(pixmap_, Thumb.pixmap_size)
            self.img_wid.setPixmap(pixmap)
            self.img_wid.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_green_text(self):
        self.setStyleSheet(
            f"""
            #{Thumb.text_obj_name} {{
                background: transparent;
                font-size: {FONT_SIZE}px;
                border-radius: {BORDER_RADIUS}px;
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
                font-size: {FONT_SIZE}px;
                border-radius: {BORDER_RADIUS}px;
                padding: 2px;
            }}
            #{Thumb.img_obj_name} {{
                background: {Static.GRAY_GLOBAL};
                font-size: {FONT_SIZE}px;
                border-radius: {self.corner}px;
            }}
            """
        )

    def set_no_frame(self):
        self.setStyleSheet(
            f"""
            #{Thumb.text_obj_name} {{
                background: transparent;
                font-size: {FONT_SIZE}px;
                border-radius: {BORDER_RADIUS}px;
                padding: 2px;
            }}
            #{Thumb.img_obj_name} {{
                background: transparent;
                font-size: {FONT_SIZE}px;
                border-radius: {self.corner}px;
            }}
            """
        )


class Grid(UScrollArea):
    spacing_value = 5

    def __init__(self, main_win_item: MainWinItem, view_index: int):
        super().__init__()
        self.setAcceptDrops(True)
        self.setWidgetResizable(True)
        self.horizontalScrollBar().setDisabled(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.is_grid_search: bool = False
        self.main_win_item = main_win_item
        self.view_index: int = view_index
        self.sort_item: SortItem = 1

        self.col_count: int = 0
        self.row: int = 0
        self.col: int = 0

        self.main_win_item = main_win_item

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

        self.origin_pos = QPoint()
        self.rubberBand = QRubberBand(QRubberBand.Rectangle, self.main_wid)
        self.wid_under_mouse: Thumb = None

        flags = Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(Grid.spacing_value)
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

    def reload_rubber(self):
        self.rubberBand.deleteLater()
        self.rubberBand = QRubberBand(QRubberBand.Rectangle, self.main_wid)

    def set_sort_item(self, sort_item: SortItem):
        if isinstance(sort_item, SortItem):
            self.sort_item = sort_item
    
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

    def path_bar_update_cmd(self, src: str):
        """
        Указывает новый путь для path_bar.py > PathBar.  
        Действие отложено по таймеру, т.к. без таймера действие может быть
        заблокировано например контекстным меню
        """
        cmd_ = lambda: self.path_bar_update_delayed(src)
        QTimer.singleShot(100, cmd_)
    
    def path_bar_update_delayed(self, src: str):
        try:
            self.path_bar_update.emit(src)
        except RuntimeError as e:
            Utils.print_error(e)
    
    def sort_thumbs(self):
        """
        Сортирует виджеты по аттрибуту BaseItem / Thumb
        """
        self.sorted_widgets = BaseItem.sort_(self.sorted_widgets, self.sort_item)
                
    def filter_thumbs(self):
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

    def resize_thumbs(self):
        """
        Изменяет размер виджетов Thumb. Подготавливает дочерние виджеты Thumb
        к новым размерам.   
        Необходимо затем вызвать метод rearrange
        """
        Thumb.calculate_size()
        for cell, wid in self.cell_to_wid.items():
            wid.setup_child_widgets()

        for i in self.selected_widgets:
            i.set_frame()

    def rearrange_thumbs(self):
        """
        Устанавливает col_count     
        Перетасовывает виджеты в сетке на основе новых условий.     
        Например был изменен размер виджета Thumb с 10x10 на 15x15,     
        соответственно число столбцов и строк в сетке виджетов Thumb    
        должно измениться, и для этого вызывается метод rearrange
        """

        # очищаем cell_to_wid, чтобы заполнить этот словарь новыми координатами
        self.cell_to_wid.clear()
        self.row, self.col = 0, 0
        self.col_count = self.get_col_count()

        # проходим циклом по отсортированным виджетам
        for wid in self.sorted_widgets:

            # соответствует методу filter_ (смотри метод filter_)
            if wid.must_hidden:
                continue

            self.grid_layout.addWidget(wid, self.row, self.col)

            # добавляем новые координаты в словарь
            self.cell_to_wid[self.row, self.col] = wid

            # меняем аттрибуты строки и столбца в виджете Thumb
            wid.row, wid.col = self.row, self.col

            self.col += 1
            if self.col >= self.col_count:
                self.col = 0
                self.row += 1

        # формируем новый словарь путь к файлу: виджет Thumb
        # на основе cell_to_wid, чтобы пропустить скрытые виджеты
        self.url_to_wid = {
            wid.src: wid
            for coords, wid in self.cell_to_wid.items()
        }

        self.total_count_update.emit(len(self.cell_to_wid))

    def add_widget_data(self, wid: Thumb, row: int, col: int):
        """
        Добавляет данные о виджете в необходимые списки и словари,
        а так же устанавливает аттрибуты Thumb: row, col
        """
        wid.row, wid.col = row, col
        self.cell_to_wid[row, col] = wid
        self.url_to_wid[wid.src] = wid
        self.sorted_widgets.append(wid)

    def view_thumb(self, wid: BaseItem):
        if len(self.selected_widgets) == 1:
            wid = self.selected_widgets[0]
            if wid.src.endswith(Static.ext_all):
                url_to_wid = {
                    url: wid
                    for url, wid in self.url_to_wid.items()
                    if url.endswith(Static.ext_all)
                }
                is_selection = False
                self.open_img_view(wid.src, url_to_wid, is_selection)
            elif wid.type_ == Static.FOLDER_TYPE:
                self.new_history_item.emit(wid.src)
                self.main_win_item.main_dir = wid.src
                self.load_st_grid.emit()
            else:
                Utils.open_in_app(wid.src)
        else:
            url_to_wid = {
                i.src: i
                for i in self.selected_widgets
                if i.src.endswith(Static.ext_all)
            }
            is_selection = True
            start_url = list(url_to_wid)[0]
            self.open_img_view(start_url, url_to_wid, is_selection)

            folders = [
                i.src
                for i in self.selected_widgets
                if i.type_ == Static.FOLDER_TYPE
            ]

            for i in folders:
                self.open_in_new_win.emit(i)

            files = [
                i.src
                for i in self.selected_widgets
                if not i.src.endswith(Static.ext_all)
                and
                i.type_ != Static.FOLDER_TYPE
            ]

            for i in files:
                Utils.open_in_app(i)

    def open_img_view(self, start_url: str, url_to_wid: dict, is_selection: bool):
        from .img_view_win import ImgViewWin
        self.win_img_view = ImgViewWin(start_url, url_to_wid, is_selection)
        self.win_img_view.move_to_wid.connect(lambda wid: self.select_one_wid(wid))
        self.win_img_view.new_rating.connect(lambda value: self.set_new_rating(value))
        self.win_img_view.closed.connect(lambda: self.img_view_closed())
        self.win_img_view.center(self.window())
        self.win_img_view.show()

    def img_view_closed(self):
        gc.collect()

    def fav_cmd(self, offset: int, src: str):
        """
        Добавляет / удаляет папку в меню избранного. Аргументы:
        - offset: -1 (удалить из избранного) или 1(добавить в избранное)
        - src: путь к папке
        """
        if 0 + offset == 1:
            self.add_fav.emit(src)
        else:
            self.del_fav.emit(src)

    def win_info_cmd(self, src: str):
        """
        Открыть окно информации о файле / папке
        """
        self.win_info = InfoWin(src)
        self.win_info.center(self.window())
        self.win_info.show()

    def show_in_folder_cmd(self, wid: Thumb):
        """
        В сетке GridSearch к каждому Thumb добавляется пункт "Показать в папке"     
        Загружает сетку GridStandart с указанным путем к файлу / папке
        """
        new_main_dir = os.path.dirname(wid.src)
        self.main_win_item.set_go_to(wid.src)
        self.main_win_item.main_dir = new_main_dir
        self.load_st_grid.emit()

    def setup_urls_to_copy(self):
        """
        Очищает список путей к файлам / папкам для последующего копирования.    
        Формирует новый список на основе списка выделенных виджетов Thumb
        """
        Dynamic.urls_to_copy.clear()
        for i in self.selected_widgets:
            Dynamic.urls_to_copy.append(i.src)

    def paste_files(self, dest: str = None):
        if not Dynamic.urls_to_copy:
            return

        if not dest:
            dest = self.main_win_item.main_dir

        for i in Dynamic.urls_to_copy:
            name = os.path.basename(i)
            new_path = os.path.join(dest, name)
            if i == new_path:
                print("нельзя копировать в себя")
                return

        self.win_copy = CopyFilesWin(dest, Dynamic.urls_to_copy)
        self.win_copy.finished_.connect(lambda files: self.paste_files_fin(files, dest))
        self.win_copy.error_.connect(self.show_error_win)
        self.win_copy.center(self.window())
        self.win_copy.show()
        QTimer.singleShot(300, self.win_copy.raise_)

    def paste_files_fin(self, files: list[str], dest: str):
        if not files:
            return
        self.main_win_item.scroll_value = self.verticalScrollBar().value()
        self.main_win_item.main_dir = dest
        self.load_st_grid.emit()
        Dynamic.urls_to_copy.clear()

    def show_error_win(self):
        """
        Открывает окно ошибки копирования файлов
        """
        self.win_copy.deleteLater()
        self.error_win = ErrorWin()
        self.error_win.center(self.window())
        self.error_win.show()

    def remove_files_cmd(self, urls: list[str]):
        """
        Окно удаления выделенных виджетов, на основе которых формируется список     
        файлов для удаления.    
        Запускается apple script remove_files.scpt через subprocess через URunnable,
        чтобы переместить файлы в корзину, а не удалять их безвозвратно.
        Окно испускет сигнал finished, что ведет к методу remove files fin
        """
        self.rem_win = RemoveFilesWin(self.main_win_item, urls)
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
        self.clear_selected_widgets()
        self.rearrange_thumbs()

    def create_new_folder(self):
        cmd = lambda name: self.create_folder_finished(name)
        self.rename_win = RenameWin("")
        self.rename_win.center(self.window())
        self.rename_win.finished_.connect(cmd)
        self.rename_win.show()
    
    def create_folder_finished(self, name: str):
        dest = os.path.join(self.main_win_item.main_dir, name)
        try:
            os.mkdir(dest)
            self.main_win_item.set_go_to(dest)
            self.load_st_grid.emit()
        except Exception as e:
            Utils.print_error(e)

    def set_new_rating(self, new_rating: int):
        """
        Устанавливает рейтинг для выделенных в сетке виджетов:
        - Делается запись в базу данных через URunnable
        - При успешной записи URunnable испускает сигнал finished
        """

        for wid in self.selected_widgets:
            self.task_ = SetDbRating(self.main_win_item.main_dir, wid, new_rating)
            cmd_ = lambda w=wid: self.set_new_rating_fin(w, new_rating)
            self.task_.signals_.finished_.connect(cmd_)
            UThreadPool.start(self.task_)

    def set_new_rating_fin(self, wid: Thumb, new_rating: int):
        """
        Устанавливает визуальный рейтинг и аттрибут рейтинга для Thumb при  
        успешной записи в базу данных
        """
        wid.rating = new_rating
        wid.rating_wid.set_text(wid)
        wid.text_changed.emit()
        
    def clear_selected_widgets(self):
        """
        Очищает список выделенных виджетов и снимает визуальное выделение с них
        """
        """
        спецагент
        """
        for i in self.selected_widgets:
            i.set_no_frame()

        self.selected_widgets.clear()

    def select_one_wid(self, wid: BaseItem | Thumb):
        """
        Очищает визуальное выделение с выделенных виджетов и очищает список.  
        Выделяет виджет, добавляет его в список выделенных виджетов.
        """
        if isinstance(wid, Thumb):
            self.path_bar_update_cmd(wid.src)
            self.clear_selected_widgets()
            wid.set_frame()
            self.selected_widgets.append(wid)

    def select_widget(self, wid: Thumb):
        """
        Добавляет виджет в список выделенных виджетов и выделяет виджет визуально.  
        Метод похож на select_one_widget, но поддерживает выделение нескольких  
        виджетов.
        """
        if isinstance(wid, Thumb):
            self.selected_widgets.append(wid)
            wid.set_frame()

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

    def set_mouseReleaseEvent(self):
        self.mouseReleaseEvent = self.mouseReleaseEvent_

    def mouseReleaseEvent_(self, a0: QMouseEvent):
        if a0.button() != Qt.MouseButton.LeftButton:
            return
        
        if self.rubberBand.isVisible():
            release_pos = self.main_wid.mapFrom(self, a0.pos())
            rect = QRect(self.origin_pos, release_pos).normalized()
            self.rubberBand.hide()
            ctrl = a0.modifiers() == Qt.KeyboardModifier.ControlModifier
            x = 10

            for wid in self.cell_to_wid.values():

                intersects = False
                inner_widgets = wid.findChildren((TextWidget, ImgFrame))

                for w in inner_widgets:
                    top_left = w.mapTo(self.main_wid, QPoint(0, 0))
                    w_rect = QRect(top_left, w.size())
                    if rect.intersects(w_rect):
                        intersects = True
                        break

                if intersects:
                    if ctrl:
                        if wid in self.selected_widgets:
                            wid.set_no_frame()
                            self.selected_widgets.remove(wid)
                        else:
                            self.select_widget(wid)
                    else:
                        if wid not in self.selected_widgets:
                            self.select_widget(wid)
                else:
                    if not ctrl and wid in self.selected_widgets:
                        wid.set_no_frame()
                        self.selected_widgets.remove(wid)
            return

        if self.wid_under_mouse is None:
            self.clear_selected_widgets()
            self.path_bar_update_cmd(self.main_win_item.main_dir)
            return
        
        if a0.modifiers() == Qt.KeyboardModifier.ShiftModifier:
            # шифт клик: если не было выделенных виджетов
            if not self.selected_widgets:
                self.select_widget(self.wid_under_mouse)
            # шифт клик: если уже был выделен один / несколько виджетов
            else:

                coords = list(self.cell_to_wid)
                start_pos = (self.selected_widgets[-1].row, self.selected_widgets[-1].col)

                # шифт клик: слева направо (по возрастанию)
                if coords.index((self.wid_under_mouse.row, self.wid_under_mouse.col)) > coords.index(start_pos):
                    start = coords.index(start_pos)
                    end = coords.index((self.wid_under_mouse.row, self.wid_under_mouse.col))
                    coords = coords[start : end + 1]

                # шифт клик: справа налево (по убыванию)
                else:
                    start = coords.index((self.wid_under_mouse.row, self.wid_under_mouse.col))
                    end = coords.index(start_pos)
                    coords = coords[start : end]

                # выделяем виджеты по срезу координат coords
                for i in coords:
                    wid_ = self.cell_to_wid.get(i)
                    if wid_ not in self.selected_widgets:
                        self.select_widget(wid=wid_)

        elif a0.modifiers() == Qt.KeyboardModifier.ControlModifier:

            # комманд клик: был выделен виджет, снять выделение
            if self.wid_under_mouse in self.selected_widgets:
                self.selected_widgets.remove(self.wid_under_mouse)
                self.wid_under_mouse.set_no_frame()

            # комманд клик: виджет не был виделен, выделить
            else:
                self.select_widget(self.wid_under_mouse)
                self.path_bar_update_cmd(self.wid_under_mouse.src)

        else:
            self.select_one_wid(self.wid_under_mouse)

    def mouseDoubleClickEvent(self, a0):
        if self.wid_under_mouse:
            self.select_one_wid(self.wid_under_mouse)
            self.view_thumb(self.wid_under_mouse)

    def mousePressEvent(self, a0):
        if a0.button() == Qt.MouseButton.LeftButton:
            self.origin_pos = self.main_wid.mapFrom(self, a0.pos())
            self.wid_under_mouse = self.get_wid_under_mouse(a0)
        return super().mousePressEvent(a0)

    def mouseMoveEvent(self, a0):
        try:
            current_pos = self.main_wid.mapFrom(self, a0.pos())
            distance = (current_pos - self.origin_pos).manhattanLength()
        except AttributeError as e:
            Utils.print_error(e)
            return

        if distance < QApplication.startDragDistance():
            return

        if self.wid_under_mouse is None and not self.rubberBand.isVisible():
            self.rubberBand.setGeometry(QRect(self.origin_pos, QSize()))
            self.rubberBand.show()

        if self.rubberBand.isVisible():
            rect = QRect(self.origin_pos, current_pos).normalized()
            self.rubberBand.setGeometry(rect)
            return

        if self.wid_under_mouse not in self.selected_widgets:
            self.select_one_wid(self.wid_under_mouse)

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
        
        if self.wid_under_mouse:
            self.path_bar_update_cmd(self.wid_under_mouse.src)

        self.drag.setMimeData(self.mime_data)
        self.drag.exec_(Qt.DropAction.CopyAction)

        return super().mouseMoveEvent(a0)

    def thumbContextActions(self, menu_: UMenu, wid: Thumb):
        # собираем пути к файлам / папкам у выделенных виджетов
        urls = [i.src for i in self.selected_widgets]
        names = [i.name for i in self.selected_widgets]
        total = len(self.selected_widgets)

        self.path_bar_update_cmd(wid.src)

        view_action = ItemActions.View(menu_)
        view_action.triggered.connect(lambda: self.view_thumb(wid))
        menu_.addAction(view_action)

        menu_.addSeparator()

        info = ItemActions.Info(menu_)
        info.triggered.connect(lambda: self.win_info_cmd(wid.src))
        menu_.addAction(info)

        show_in_finder_action = ItemActions.RevealInFinder(menu_, urls, total)
        menu_.addAction(show_in_finder_action)

        copy_path = ItemActions.CopyPath(menu_, urls, total)
        menu_.addAction(copy_path)

        copy_name = ItemActions.CopyName(menu_, names, total)
        menu_.addAction(copy_name)

        copy_files = ItemActions.CopyObjects(menu_, total)
        copy_files.triggered.connect(self.setup_urls_to_copy)
        menu_.addAction(copy_files)

        menu_.addSeparator()

        if wid.type_ == Static.FOLDER_TYPE:
            if wid.src in JsonData.favs:
                cmd_ = lambda: self.fav_cmd(offset=-1, src=wid.src)
                fav_action = ItemActions.FavRemove(menu_)
                fav_action.triggered.connect(cmd_)
                menu_.addAction(fav_action)
            else:
                cmd_ = lambda: self.fav_cmd(offset=1, src=wid.src)
                fav_action = ItemActions.FavAdd(menu_)
                fav_action.triggered.connect(cmd_)
                menu_.addAction(fav_action)

            menu_.addSeparator()

        rating_menu = ItemActions.RatingMenu(menu_, urls, total, wid.rating)
        rating_menu.new_rating.connect(self.set_new_rating)
        menu_.addMenu(rating_menu)

        menu_.addSeparator()

        # is grid search устанавливается на True при инициации GridSearch
        if self.is_grid_search:
            show_in_folder = ItemActions.ShowInGrid(menu_)
            cmd_ = lambda: self.show_in_folder_cmd(wid)
            show_in_folder.triggered.connect(cmd_)
            menu_.addAction(show_in_folder)
            menu_.addSeparator()

        menu_.addSeparator()

        remove_files = ItemActions.RemoveObjects(menu_, total)
        remove_files.triggered.connect(lambda: self.remove_files_cmd(urls))
        menu_.addAction(remove_files)

    def gridContexActions(self, menu_: UMenu):
        self.path_bar_update_cmd(self.main_win_item.main_dir)

        names = [os.path.basename(self.main_win_item.main_dir)]
        urls = [self.main_win_item.main_dir]
        total = 1

        new_folder = GridActions.NewFolder(menu_)
        new_folder.triggered.connect(self.create_new_folder)
        menu_.addAction(new_folder)

        menu_.addSeparator()

        info = GridActions.Info(menu_)
        info.triggered.connect(lambda: self.win_info_cmd(self.main_win_item.main_dir))
        menu_.addAction(info)

        reveal = GridActions.RevealInFinder(menu_, urls, total)
        menu_.addAction(reveal)

        copy_ = GridActions.CopyPath(menu_, urls, total)
        menu_.addAction(copy_)

        copy_name = GridActions.CopyName(menu_, names, total)
        menu_.addAction(copy_name)

        menu_.addSeparator()

        if self.main_win_item.main_dir in JsonData.favs:
            cmd_ = lambda: self.fav_cmd(-1, self.main_win_item.main_dir)
            fav_action = GridActions.FavRemove(menu_)
            fav_action.triggered.connect(cmd_)
            menu_.addAction(fav_action)

        else:
            cmd_ = lambda: self.fav_cmd(+1, self.main_win_item.main_dir)
            fav_action = GridActions.FavAdd(menu_)
            fav_action.triggered.connect(cmd_)
            menu_.addAction(fav_action)

        menu_.addSeparator()

        change_view = GridActions.ChangeViewMenu(menu_, self.view_index)
        change_view.change_view_sig.connect(self.change_view.emit)
        menu_.addMenu(change_view)

        sort_menu = GridActions.SortMenu(menu_, self.sort_item)
        sort_menu.sort_grid_sig.connect(lambda: self.sort_thumbs())
        sort_menu.rearrange_grid_sig.connect(lambda: self.rearrange_thumbs())
        sort_menu.sort_menu_update.connect(lambda: self.sort_menu_update.emit())
        menu_.addMenu(sort_menu)

        menu_.addSeparator()

        if Dynamic.urls_to_copy and not self.is_grid_search:
            paste_files = GridActions.PasteObjects(menu_, len(Dynamic.urls_to_copy))
            paste_files.triggered.connect(self.paste_files)
            menu_.addAction(paste_files)

        upd_ = GridActions.UpdateGrid(menu_)
        upd_.triggered.connect(lambda: self.load_st_grid.emit())
        menu_.addAction(upd_)

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
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
                    self.wid_under_mouse = self.selected_widgets[-1]
                    if self.wid_under_mouse:
                        self.select_one_wid(self.wid_under_mouse)
                        self.view_thumb(self.wid_under_mouse)

            elif a0.key() == Qt.Key.Key_I:
                if self.selected_widgets:
                    self.wid_under_mouse = self.selected_widgets[-1]
                    self.select_one_wid(self.wid_under_mouse)
                    self.win_info_cmd(self.wid_under_mouse.src)
                else:
                    self.win_info_cmd(self.main_win_item.main_dir)

            elif a0.key() == Qt.Key.Key_Equal:
                new_value = Dynamic.pixmap_size_ind + 1
                if new_value <= len(ThumbData.PIXMAP_SIZE) - 1:
                    self.move_slider.emit(new_value)

            elif a0.key() == Qt.Key.Key_Minus:
                new_value = Dynamic.pixmap_size_ind - 1
                if new_value >= 0:
                    self.move_slider.emit(new_value)

            elif a0.key() == Qt.Key.Key_A:
                self.clear_selected_widgets()
                for cell, wid in self.cell_to_wid.items():
                    self.select_widget(wid)

            elif a0.key() == Qt.Key.Key_Backspace:
                urls = [i.src for i in self.selected_widgets]
                self.remove_files_cmd(urls)

        elif a0.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return):
            if self.selected_widgets:
                self.wid_under_mouse = self.selected_widgets[-1]
                if self.wid_under_mouse:
                    self.view_thumb(self.wid_under_mouse)

        elif a0.key() in KEY_NAVI:
            offset = KEY_NAVI.get(a0.key())

            # если не выделено ни одного виджета
            if not self.selected_widgets:
                self.wid_under_mouse = self.cell_to_wid.get((0, 0))
                if len(self.sorted_widgets) == 1:
                    self.select_one_wid(self.wid_under_mouse)
                    return
            else:
                self.wid_under_mouse = self.selected_widgets[-1]

            # если нет даже первого виджета значит сетка пуста
            if not self.wid_under_mouse:
                return

            coords = (
                self.wid_under_mouse.row + offset[0], 
                self.wid_under_mouse.col + offset[1]
            )

            next_wid = self.cell_to_wid.get(coords)

            if next_wid is None:
                if a0.key() == Qt.Key.Key_Right:
                    coords = (
                        self.wid_under_mouse.row + 1, 
                        0
                    )
                elif a0.key() == Qt.Key.Key_Left:
                    coords = (
                        self.wid_under_mouse.row - 1,
                        self.col_count - 1
                    )
                next_wid = self.cell_to_wid.get(coords)

            if next_wid:
                self.select_one_wid(next_wid)
                self.ensureWidgetVisible(next_wid)
                self.wid_under_mouse = next_wid

        elif a0.key() in KEY_RATING:
            rating = KEY_RATING.get(a0.key())
            self.set_new_rating(rating)
        
        return super().keyPressEvent(a0)

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:
        menu_ = UMenu(parent=self)
        self.wid_under_mouse = self.get_wid_under_mouse(a0)

        # клик по пустому пространству
        if not self.wid_under_mouse:
            self.clear_selected_widgets()
            self.gridContexActions(menu_)

        # клик по виджету
        else:
            # если не было выделено ни одного виджет ранее
            # то выделяем кликнутый
            if not self.selected_widgets:
                self.select_widget(self.wid_under_mouse)
            # если есть выделенные виджеты, но кликнутый виджет не выделены
            # то снимаем выделение с других и выделяем кликнутый
            elif self.wid_under_mouse not in self.selected_widgets:
                self.clear_selected_widgets()
                self.select_widget(self.wid_under_mouse)
            
            if isinstance(self.wid_under_mouse, (BaseItem, Thumb)):
                self.thumbContextActions(menu_, self.wid_under_mouse)
            else:
                self.gridContexActions(menu_)

        menu_.show_()
    
    def dragEnterEvent(self, a0):
        if self.is_grid_search:
            return
        if a0.mimeData().hasUrls():
            a0.acceptProposedAction()
        return super().dragEnterEvent(a0)
    
    def dropEvent(self, a0):
        Dynamic.urls_to_copy.clear()
        Dynamic.urls_to_copy = [i.toLocalFile() for i in a0.mimeData().urls()]

        main_dir_ = Utils.normalize_slash(self.main_win_item.main_dir)
        sys_vol = Utils.get_system_volume(Static.APP_SUPPORT_APP)
        main_dir_ = Utils.add_system_volume(main_dir_, sys_vol)
        for i in Dynamic.urls_to_copy:
            i = Utils.normalize_slash(i)
            i = Utils.add_system_volume(i, sys_vol)
            if os.path.commonpath([i, main_dir_]) == main_dir_:
                print("Нельзя копировать в себя")
                return

        if Dynamic.urls_to_copy:
            self.paste_files()

        return super().dropEvent(a0)
