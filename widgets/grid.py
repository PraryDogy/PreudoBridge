import gc
import os
import shutil

from PyQt5.QtCore import (QMimeData, QPoint, QRect, QSize, Qt, QTimer, QUrl,
                          pyqtSignal)
from PyQt5.QtGui import (QContextMenuEvent, QDrag, QKeyEvent, QMouseEvent,
                         QPixmap)
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import (QApplication, QFrame, QGridLayout, QLabel,
                             QRubberBand, QSplitter, QVBoxLayout, QWidget)

from cfg import Dynamic, JsonData, Static, ThumbData
from evlosh_templates.evlosh_utils import EvloshUtils
from system.items import BaseItem, CopyItem, MainWinItem, SortItem
from system.tasks import LoadImagesTask, RatingTask
from system.utils import ImageUtils, UThreadPool, Utils

from ._base_widgets import UMenu, UScrollArea
from .actions import GridActions, ItemActions
from .copy_files_win import CopyFilesWin, ErrorWin
from .img_convert_win import ImgConvertWin
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


class ImgFrameWidget(QFrame):
    def __init__(self):
        super().__init__()


class FileNameWidget(QLabel):
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


class RatingWidget(QLabel):
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
    
    def set_text(self, rating: int, type_: str, mod: int, size: int):
        try:
            self._set_text(rating, type_, mod, size)
        except Exception:
            Utils.print_error()

    def _set_text(self, rating: int, type_: str, mod: int, size: int):
        if rating > 0:
            mod_row = RATINGS.get(rating).strip()
        else:
            mod_row = self.text_mod + EvloshUtils.get_f_date(mod)
            if type_ == Static.FOLDER_TYPE:
                sec_row = str("")
            else:
                sec_row = self.text_size + EvloshUtils.get_f_size(size, 0)
            mod_row = "\n".join((mod_row, sec_row))
        self.setText(mod_row)


class Thumb(BaseItem, QFrame):
    # Сигнал нужен, чтобы менялся заголовок в просмотрщике изображений
    # При изменении рейтинга или меток
    text_changed = pyqtSignal()
    pixmap_size: int = 0
    thumb_w: int = 0
    thumb_h: int = 0
    corner: int = 0
    img_obj_name: str = "img_frame"
    text_obj_name: str = "text_frame_"

    def __init__(self, src: str, rating: int = 0):
        """
        опционально:
        migrate_from_base_item(base_item)
        set_properties

        обязательно:
        set_widget_size()
        set_no_frame()
        set_generic_icon()
        """
    
        QFrame.__init__(self, parent=None)
        BaseItem.__init__(self, src, rating)

        self.must_hidden: bool = False
        self.row, self.col = 0, 0

        self.v_lay = QVBoxLayout()
        self.v_lay.setContentsMargins(0, 0, 0, 0)
        self.v_lay.setSpacing(ThumbData.SPACING)
        self.v_lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setLayout(self.v_lay)

        self.img_frame = ImgFrameWidget()
        self.img_frame.setObjectName(Thumb.img_obj_name)
        self.v_lay.addWidget(self.img_frame, alignment=Qt.AlignmentFlag.AlignCenter)

        self.img_frame_lay = QVBoxLayout()
        self.img_frame_lay.setContentsMargins(0, 0, 0, 0)
        self.img_frame_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_frame.setLayout(self.img_frame_lay)

        self.img_wid = QSvgWidget()
        self.img_frame_lay.addWidget(self.img_wid)

        self.text_wid = FileNameWidget()
        self.text_wid.setObjectName(Thumb.text_obj_name)
        self.v_lay.addWidget(self.text_wid, alignment=Qt.AlignmentFlag.AlignCenter)

        self.rating_wid = RatingWidget()
        self.v_lay.addWidget(self.rating_wid, alignment=Qt.AlignmentFlag.AlignCenter)
    
    @classmethod
    def calc_size(cls):
        ind = Dynamic.pixmap_size_ind
        cls.pixmap_size = ThumbData.PIXMAP_SIZE[ind]
        cls.img_frame_size = Thumb.pixmap_size + ThumbData.OFFSET
        cls.thumb_w = ThumbData.THUMB_W[ind]
        cls.thumb_h = ThumbData.THUMB_H[ind]
        cls.corner = ThumbData.CORNER[ind]

    def set_generic_icon(self):
        if self.src.count(os.sep) == 2:
            path = Static.HDD_SVG
        else:
            path = Utils.get_generic_icon_path(self.type_, Static.GENERIC_ICONS_DIR)
        self.img_wid.load(path)
        self.img_wid.setFixedSize(Thumb.pixmap_size, Thumb.pixmap_size)

    def set_pixmap(self, pixmap: QPixmap):
        self.img_wid.deleteLater()
        self.img_wid = QLabel()
        scaled_pixmap = ImageUtils.pixmap_scale(pixmap, Thumb.pixmap_size)
        self.img_wid.setPixmap(scaled_pixmap)
        self.img_frame_lay.addWidget(self.img_wid, alignment=Qt.AlignmentFlag.AlignCenter)

    def migrate_from_base_item(self, base_item: BaseItem):
        """
        Позволяет перенести данные из BaseItem в Thumb.
        """
        self.src = base_item.src
        self.filename = base_item.filename
        self.type_ = base_item.type_
        self.mod = base_item.mod
        self.birth = base_item.birth
        self.size = base_item.size
        self.rating = base_item.rating

    def set_widget_size(self):
        """
        Устанавливает фиксированные размеры для дочерних виджетов Thumb     
        Устанавливает текст в дочерних виджетах в соответствии с размерами  
        Устанавливает изображение в дочерних виджетах в соответствии в размерами
        """
        self.text_wid.set_text(self.filename)
        self.rating_wid.set_text(self.rating, self.type_, self.mod, self.size)

        self.setFixedSize(Thumb.thumb_w, Thumb.thumb_h)
        self.img_wid.setFixedSize(Thumb.pixmap_size, Thumb.pixmap_size)
        self.img_frame.setFixedSize(Thumb.img_frame_size, Thumb.img_frame_size)

        if self.get_pixmap_storage():
            pixmap = self.get_pixmap_storage()
            pixmap = ImageUtils.pixmap_scale(pixmap, Thumb.pixmap_size)
            self.img_wid.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.img_wid.setPixmap(pixmap)

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
    new_files_key = "new_files"
    del_files_key = "del files"

    new_history_item = pyqtSignal(str)
    path_bar_update = pyqtSignal(str)
    add_fav = pyqtSignal(str)
    del_fav = pyqtSignal(str)
    load_st_grid = pyqtSignal()
    move_slider = pyqtSignal(int)
    change_view = pyqtSignal()
    open_in_new_win = pyqtSignal(tuple)
    level_up = pyqtSignal()
    sort_menu_update = pyqtSignal()
    total_count_update = pyqtSignal(tuple)
    finished_ = pyqtSignal()

    def __init__(self, main_win_item: MainWinItem):
        super().__init__()
        self.setAcceptDrops(True)
        self.setWidgetResizable(True)
        self.horizontalScrollBar().setDisabled(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.is_grid_search: bool = False
        self.main_win_item: MainWinItem = main_win_item
        self.sort_item: SortItem = 1
        self.col_count: int = 0
        self.row: int = 0
        self.col: int = 0
        self.url_to_wid: dict[str, Thumb] = {}
        self.cell_to_wid: dict[tuple, Thumb] = {}
        self.selected_thumbs: list[Thumb] = []
        self.already_loaded_thumbs: list[Thumb] = []
        self.load_images_tasks: list[LoadImagesTask] = []
        self.wid_under_mouse: Thumb = None

        self.main_wid = QWidget()
        self.setWidget(self.main_wid)
        self.origin_pos = QPoint()
        self.rubberBand = QRubberBand(QRubberBand.Rectangle, self.main_wid)

        flags = Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(self.spacing_value)
        self.grid_layout.setAlignment(flags)
        self.main_wid.setLayout(self.grid_layout)

        self.st_mtime = self.get_st_mtime(self.main_win_item.main_dir)
        self.st_mtime_timer = QTimer(self)
        self.st_mtime_timer.setSingleShot(True)
        self.st_mtime_timer.timeout.connect(lambda: self.check_dir_mod())
        self.st_mtime_timer.start(100)

    def get_st_mtime(self, url: str):
        try:
            return os.stat(url).st_mtime
        except Exception:
            # Utils.print_error()
            print("grid > get st mtime > file not found", url)
            return None

    def check_dir_mod(self):
        """
        Проверяет, изменилось ли время модификации главной директории.
        Если изменилось — вызывает обновление изменённых Thumb.
        Повторяет проверку каждые 2 секунды.
        """
        self.st_mtime_timer.stop()
        new_st_mtime = self.get_st_mtime(self.main_win_item.main_dir)

        if new_st_mtime:
            if new_st_mtime != self.st_mtime:
                self.st_mtime = new_st_mtime
                self.update_mod_thumbs()
            self.st_mtime_timer.start(2000)

    def update_mod_thumbs(self) -> list[Thumb]:
        """
        Обходит все Thumb и обновляет те, у которых изменилось
        время модификации. Возвращает список изменённых Thumb.
        """
        thumbs: list[Thumb] = []
        for thumb in self.url_to_wid.values():
            new_mod = self.get_st_mtime(thumb.src)
            if new_mod and thumb.mod != new_mod:
                thumb.set_properties()
                thumb.rating_wid.set_text(thumb.rating, thumb.type_, thumb.mod, thumb.size)
                thumbs.append(thumb)
        return thumbs

    def start_load_images_task(self, thumbs: list[Thumb]):
        """
        Запускает фоновую задачу загрузки изображений для списка Thumb.
        Изображения загружаются из базы данных или из директории, если в БД нет.
        """
        def finalize(task: LoadImagesTask):
            if task in self.load_images_tasks:
                self.load_images_tasks.remove(task)

        def set_thumb_image(thumb: Thumb):
            if thumb.get_pixmap_storage():
                try:
                    thumb.set_pixmap(thumb.get_pixmap_storage())
                    self.already_loaded_thumbs.append(thumb)
                except RuntimeError as e:
                    Utils.print_error()

        for i in self.load_images_tasks:
            i.set_should_run(False)
        task_ = LoadImagesTask(self.main_win_item, thumbs)
        task_.signals_.update_thumb.connect(set_thumb_image)
        task_.signals_.finished_.connect(lambda: finalize(task_))
        self.load_images_tasks.append(task_)
        UThreadPool.start(task_)
    
    def reload_rubber(self):
        self.rubberBand.deleteLater()
        self.rubberBand = QRubberBand(QRubberBand.Rectangle, self.main_wid)
    
    def get_clmn_count(self):
        """
        Получает количество столбцов для сетки по формуле:  
        Ширина окна минус ширина левого виджета в сплиттере (левое меню)
        """
        win_ww = self.window().width()
        splitter = self.window().findChild(QSplitter)
        if splitter:
            left_menu: QWidget = splitter.children()[1]
            left_menu_ww = left_menu.width()
            return (win_ww - left_menu_ww) // Thumb.thumb_w
        else:
            return 1

    def path_bar_update_delayed(self, src: str):
        """
        Указывает новый путь для path_bar.py > PathBar.  
        Действие отложено по таймеру, т.к. без таймера действие может быть
        заблокировано например контекстным меню
        """
        def path_bar_update_delayed():
            try:
                self.path_bar_update.emit(src)
            except RuntimeError as e:
                Utils.print_error()
        QTimer.singleShot(0, path_bar_update_delayed)
    
    def sort_thumbs(self):
        """
        Сортирует виджеты по аттрибуту BaseItem / Thumb
        """
        thumb_list = list(self.url_to_wid.values())
        thumb_list = BaseItem.sort_items(thumb_list, self.sort_item)
        wid_to_url = {v: k for k, v in self.url_to_wid.items()}
        self.url_to_wid = {
            wid_to_url[thumb]: thumb
            for thumb in thumb_list
        }
                
    def filter_thumbs(self):
        """
        Скрывает виджеты, не соответствующие установленному фильтру.    
        Например, если фильтр установлен "отобразить 5 звезд",     
        то будут отображены только виджеты с рейтингом 5, остальные скрыты,     
        но не удалены.  
        Необходимо затем вызвать метод rearrange
        """
        for wid in self.url_to_wid.values():
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
        Thumb.calc_size()
        for wid in self.url_to_wid.values():
            wid.set_widget_size()
        for i in self.selected_thumbs:
            i.set_frame()

    def rearrange_thumbs(self):
        """
        Устанавливает col_count     
        Перетасовывает виджеты в сетке на основе новых условий.     
        Например был изменен размер виджета Thumb с 10x10 на 15x15,     
        соответственно число столбцов и строк в сетке виджетов Thumb    
        должно измениться, и для этого вызывается метод rearrange
        """
        self.cell_to_wid.clear()
        self.row, self.col = 0, 0
        self.col_count = self.get_clmn_count()
        for wid in self.url_to_wid.values():
            if wid.must_hidden:
                continue
            self.grid_layout.addWidget(wid, self.row, self.col)
            self.add_widget_data(wid, self.row, self.col)
            self.col += 1
            if self.col >= self.col_count:
                self.col = 0
                self.row += 1
        self.total_count_update.emit((len(self.selected_thumbs), len(self.cell_to_wid)))

    def add_widget_data(self, wid: Thumb, row: int, col: int):
        """
        Устанавливает thumb.row, thumb.col
        Добавляет thumb в cell to wid, url to wid
        """
        wid.row, wid.col = row, col
        self.cell_to_wid[row, col] = wid
        self.url_to_wid[wid.src] = wid

    def open_thumb(self):
        if len(self.selected_thumbs) == 1:
            wid = self.selected_thumbs[0]
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
                Utils.open_in_def_app(wid.src)
        else:
            url_to_wid = {
                i.src: i
                for i in self.selected_thumbs
                if i.src.endswith(Static.ext_all)
            }
            if url_to_wid:
                is_selection = True
                start_url = list(url_to_wid)[0]
                self.open_img_view(start_url, url_to_wid, is_selection)

            folders = [
                i.src
                for i in self.selected_thumbs
                if i.type_ == Static.FOLDER_TYPE
            ]

            for i in folders:
                self.open_in_new_win.emit((i, None))

            files = [
                i.src
                for i in self.selected_thumbs
                if not i.src.endswith(Static.ext_all)
                and
                i.type_ != Static.FOLDER_TYPE
            ]

            for i in files:
                Utils.open_in_def_app(i)

    def open_img_view(self, start_url: str, url_to_wid: dict, is_selection: bool):

        def on_close():
            del self.win_img_view
            gc.collect()

        def set_db_rating(data: tuple):
            rating, url = data
            wid = self.url_to_wid.get(url)
            if not wid:
                return
            self.rating_task = RatingTask(self.main_win_item.main_dir, wid.filename, rating)
            cmd_ = lambda: self.set_thumb_rating(wid, rating)
            self.rating_task.signals_.finished_.connect(cmd_)
            UThreadPool.start(self.rating_task)

        from .img_view_win import ImgViewWin
        self.win_img_view = ImgViewWin(start_url, url_to_wid, is_selection)
        self.win_img_view.move_to_wid.connect(self.select_single_thumb)
        self.win_img_view.new_rating.connect(set_db_rating)
        self.win_img_view.closed.connect(on_close)
        self.win_img_view.center(self.window())
        self.win_img_view.show()

    def fav_cmd(self, offset: int, src: str):
        """
        Добавляет / удаляет папку в меню избранного. Аргументы:
        - offset: -1 (удалить из избранного) или 1(добавить в избранное)
        - src: путь к папке
        """
        (self.add_fav if offset == 1 else self.del_fav).emit(src)

    def open_win_info(self, src: str):
        """
        Открыть окно информации о файле / папке
        """
        def finalize(win_info: InfoWin):
            win_info.center(self.window())
            win_info.show()
        self.win_info = InfoWin(src)
        self.win_info.finished_.connect(lambda: finalize(self.win_info))

    def show_in_folder_cmd(self, wid: Thumb):
        """
        В сетке GridSearch к каждому Thumb добавляется пункт "Показать в папке"     
        Загружает сетку GridStandart с указанным путем к файлу / папке
        """
        def cmd(main_dir: str):
            self.open_in_new_win.emit((main_dir, [wid.src, ]))

        new_main_dir = os.path.dirname(wid.src)
        QTimer.singleShot(100, lambda: cmd(new_main_dir))

    def setup_urls_to_copy(self):
        """
        Очищает список путей к файлам / папкам для последующего копирования.    
        Формирует новый список на основе списка выделенных виджетов Thumb
        """
        CopyItem.urls.clear()
        CopyItem.set_src(self.main_win_item.main_dir)
        CopyItem.set_is_search(self.is_grid_search)
        for i in self.selected_thumbs:
            CopyItem.urls.append(i.src)
            if CopyItem.get_is_cut():
                self.del_thumb(i.src)
        self.rearrange_thumbs()

    def paste_files(self):

        def scroll_to_wid():
            self.ensureWidgetVisible(self.selected_thumbs[-1])

        def paste_final(urls: list[str]):
            thumbs = []
            empty_grid = not self.cell_to_wid
            self.clear_selected_widgets()
            for i in urls:
                self.del_thumb(i)
                thumb = self.new_thumb(i)
                self.select_multiple_thumb(thumb)
                thumbs.append(thumb)
            if empty_grid:
                self.load_st_grid.emit()
            else:
                self.rearrange_thumbs()
                self.start_load_images_task(thumbs)
                if self.selected_thumbs:
                    QTimer.singleShot(50, scroll_to_wid)

        def show_error_win():
            self.win_copy.deleteLater()
            self.error_win = ErrorWin()
            self.error_win.center(self.window())
            self.error_win.show()
        
        CopyItem.set_dest(self.main_win_item.main_dir)
        self.win_copy = CopyFilesWin()
        self.win_copy.finished_.connect(paste_final)
        self.win_copy.error_win.connect(show_error_win)
        self.win_copy.center(self.window())
        self.win_copy.show()
        QTimer.singleShot(300, self.win_copy.raise_)

    def load_visible_images(self):
        """
        Составляет список Thumb виджетов, которые находятся в зоне видимости.   
        Запускает загрузку изображений через URunnable
        """
        thumbs: list[Thumb] = []
        for thumb in self.url_to_wid.values():
            if not thumb.visibleRegion().isEmpty():
                if thumb not in self.already_loaded_thumbs:
                    thumbs.append(thumb)
        if thumbs:
            for i in self.load_images_tasks:
                i.set_should_run(False)
            self.start_load_images_task(thumbs)

    def remove_files(self, urls: list[str]):

        def finalize(urls: list[str]):
            # вычисляем индекс последнего выделенного виджета
            all_urls = list(self.url_to_wid)
            ind = all_urls.index(self.selected_thumbs[-1].src)
            for url in urls:
                self.del_thumb(url)
            all_urls = list(self.url_to_wid)
            if all_urls:
                try:
                    new_url = all_urls[ind]
                except IndexError:
                    new_url = all_urls[-1]
                new_wid = self.url_to_wid.get(new_url)
                self.select_single_thumb(new_wid)
            self.rearrange_thumbs()
            # например ты удалил виджет и стала видна следующая строка
            # с виджетами, где картинки еще не были загружены
            self.load_visible_images()
            if not self.cell_to_wid:
                self.load_st_grid.emit()

        self.rem_win = RemoveFilesWin(self.main_win_item, urls)
        self.rem_win.finished_.connect(finalize)
        self.rem_win.center(self.window())
        self.rem_win.show()

    def new_thumb(self, url: str):
        thumb = Thumb(url)
        thumb.set_properties()
        thumb.set_widget_size()
        thumb.set_no_frame()
        thumb.set_generic_icon()
        self.add_widget_data(thumb, self.row, self.col)
        self.grid_layout.addWidget(thumb, self.row, self.col)

        self.col += 1
        if self.col >= self.col_count:
            self.col = 0
            self.row += 1

        return thumb

    def del_thumb(self, url: str):
        wid = self.url_to_wid.get(url)
        if not wid:
            return
        if wid in self.selected_thumbs:
            self.selected_thumbs.remove(wid)
        if wid in self.already_loaded_thumbs:
            self.already_loaded_thumbs.remove(wid)
        self.cell_to_wid.pop((wid.row, wid.col))
        self.url_to_wid.pop(url)
        wid.deleteLater()

    def set_thumb_rating(self, wid: Thumb, new_rating: int):
        wid.rating = new_rating
        wid.rating_wid.set_text(wid.rating, wid.type_, wid.mod, wid.size)
        wid.text_changed.emit()

    def new_rating_multiple_start(self, rating: int):
        """
        Устанавливает рейтинг для выделенных в сетке виджетов:
        - Делается запись в базу данных через URunnable
        - При успешной записи URunnable испускает сигнал finished
        """

        for wid in self.selected_thumbs:
            self.rating_task = RatingTask(self.main_win_item.main_dir, wid.filename, rating)
            cmd_ = lambda w=wid: self.set_thumb_rating(w, rating)
            self.rating_task.signals_.finished_.connect(cmd_)
            UThreadPool.start(self.rating_task)
        
    def clear_selected_widgets(self):
        """
        Очищает список выделенных виджетов и снимает визуальное выделение с них
        """
        for i in self.selected_thumbs:
            i.set_no_frame()
        self.selected_thumbs.clear()

    def select_single_thumb(self, wid: BaseItem | Thumb):
        """
        Очищает визуальное выделение с выделенных виджетов и очищает список.  
        Выделяет виджет, добавляет его в список выделенных виджетов.
        """
        if isinstance(wid, Thumb):
            self.path_bar_update_delayed(wid.src)
            self.clear_selected_widgets()
            wid.set_frame()
            self.selected_thumbs.append(wid)

    def select_multiple_thumb(self, wid: Thumb):
        """
        Добавляет виджет в список выделенных виджетов и выделяет виджет визуально.  
        Метод похож на select_one_widget, но поддерживает выделение нескольких  
        виджетов.
        """
        if isinstance(wid, Thumb):
            self.selected_thumbs.append(wid)
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

        if isinstance(wid, (FileNameWidget, RatingWidget, ImgFrameWidget)):
            return wid.parent()
        elif isinstance(wid, (QLabel, QSvgWidget)):
            return wid.parent().parent()
        else:
            return None

    def open_img_convert_win(self, urls: list[str]):

        def finished_(urls: list[str]):
            self.convert_win.deleteLater()
            if urls:
                self.main_win_item.set_urls_to_select(urls)
                self.load_st_grid.emit()

        self.convert_win = ImgConvertWin(urls)
        self.convert_win.center(self.window())
        self.convert_win.finished_.connect(lambda urls: finished_(urls))
        self.convert_win.show()

    def mouseReleaseEvent(self, a0: QMouseEvent):
        if a0.button() != Qt.MouseButton.LeftButton:
            return
        
        elif self.rubberBand.isVisible():
            release_pos = self.main_wid.mapFrom(self, a0.pos())
            rect = QRect(self.origin_pos, release_pos).normalized()
            self.rubberBand.hide()
            ctrl = a0.modifiers() in (Qt.KeyboardModifier.ControlModifier, Qt.KeyboardModifier.ShiftModifier)
            for wid in self.cell_to_wid.values():
                intersects = False
                inner_widgets = wid.findChildren((FileNameWidget, ImgFrameWidget))
                for w in inner_widgets:
                    top_left = w.mapTo(self.main_wid, QPoint(0, 0))
                    w_rect = QRect(top_left, w.size())
                    if rect.intersects(w_rect):
                        intersects = True
                        break
                if intersects:
                    if ctrl:
                        if wid in self.selected_thumbs:
                            wid.set_no_frame()
                            self.selected_thumbs.remove(wid)
                        else:
                            self.select_multiple_thumb(wid)
                    else:
                        if wid not in self.selected_thumbs:
                            self.select_multiple_thumb(wid)
                else:
                    if not ctrl and wid in self.selected_thumbs:
                        wid.set_no_frame()
                        self.selected_thumbs.remove(wid)

        elif self.wid_under_mouse is None:
            self.clear_selected_widgets()
            self.path_bar_update_delayed(self.main_win_item.main_dir)
        
        elif a0.modifiers() == Qt.KeyboardModifier.ShiftModifier:
            # шифт клик: если не было выделенных виджетов
            if not self.selected_thumbs:
                self.select_multiple_thumb(self.wid_under_mouse)
            # шифт клик: если уже был выделен один / несколько виджетов
            else:
                coords = list(self.cell_to_wid)
                start_pos = (self.selected_thumbs[-1].row, self.selected_thumbs[-1].col)
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
                    if wid_ not in self.selected_thumbs:
                        self.select_multiple_thumb(wid=wid_)

        elif a0.modifiers() == Qt.KeyboardModifier.ControlModifier:
            # комманд клик: был выделен виджет, снять выделение
            if self.wid_under_mouse in self.selected_thumbs:
                self.selected_thumbs.remove(self.wid_under_mouse)
                self.wid_under_mouse.set_no_frame()
            # комманд клик: виджет не был виделен, выделить
            else:
                self.select_multiple_thumb(self.wid_under_mouse)
                self.path_bar_update_delayed(self.wid_under_mouse.src)
        else:
            self.select_single_thumb(self.wid_under_mouse)

        self.total_count_update.emit((len(self.selected_thumbs), len(self.cell_to_wid)))

    def mouseDoubleClickEvent(self, a0):
        if self.wid_under_mouse:
            self.select_single_thumb(self.wid_under_mouse)
            self.open_thumb()

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
            Utils.print_error()
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

        if self.wid_under_mouse not in self.selected_thumbs:
            self.select_single_thumb(self.wid_under_mouse)

        urls = [
            i.src
            for i in self.selected_thumbs
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
            self.path_bar_update_delayed(self.wid_under_mouse.src)

        self.total_count_update.emit((len(self.selected_thumbs), len(self.cell_to_wid)))
        self.drag.setMimeData(self.mime_data)
        self.drag.exec_(Qt.DropAction.CopyAction)

        return super().mouseMoveEvent(a0)

    def context_thumb(self, menu_: UMenu, wid: Thumb):
        # собираем пути к файлам / папкам у выделенных виджетов
        urls = [i.src for i in self.selected_thumbs]
        urls_img = [i.src for i in self.selected_thumbs if i.src.endswith(Static.ext_all)]
        names = [i.filename for i in self.selected_thumbs]
        total = len(self.selected_thumbs)
        self.path_bar_update_delayed(wid.src)

        view_action = ItemActions.OpenThumb(menu_)
        view_action.triggered.connect(lambda: self.open_thumb())
        menu_.addAction(view_action)

        if wid.type_ != Static.FOLDER_TYPE:
            open_in_app = ItemActions.OpenInApp(menu_, urls)
            menu_.addMenu(open_in_app)
        else:
            new_win = ItemActions.OpenInNewWindow(menu_)
            new_win.triggered.connect(lambda: self.open_in_new_win.emit((wid.src, None)))
            menu_.addAction(new_win)

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

            rating_menu = ItemActions.RatingMenu(menu_, wid.rating)
            rating_menu.new_rating.connect(self.new_rating_multiple_start)
            menu_.addMenu(rating_menu)

        info = ItemActions.Info(menu_)
        info.triggered.connect(lambda: self.open_win_info(wid.src))
        menu_.addAction(info)

        if wid.type_ in Static.ext_all and not self.is_grid_search:
            convert_action = ItemActions.ImgConvert(menu_)
            convert_action.triggered.connect(lambda: self.open_img_convert_win(urls_img))
            menu_.addAction(convert_action)

        # is grid search устанавливается на True при инициации GridSearch
        if self.is_grid_search:
            show_in_folder = ItemActions.ShowInGrid(menu_)
            cmd_ = lambda: self.show_in_folder_cmd(wid)
            show_in_folder.triggered.connect(cmd_)
            menu_.addAction(show_in_folder)

        menu_.addSeparator()

        show_in_finder_action = ItemActions.RevealInFinder(menu_, urls)
        menu_.addAction(show_in_finder_action)

        copy_path = ItemActions.CopyPath(menu_, urls)
        copy_path.triggered.connect(lambda: CopyItem.reset())
        menu_.addAction(copy_path)

        copy_name = ItemActions.CopyName(menu_, names)
        copy_name.triggered.connect(lambda: CopyItem.reset())
        menu_.addAction(copy_name)

        menu_.addSeparator()

        cut_objects = ItemActions.CutObjects(menu_)
        cut_objects.triggered.connect(lambda: CopyItem.set_is_cut(True))
        cut_objects.triggered.connect(self.setup_urls_to_copy)
        menu_.addAction(cut_objects)

        copy_files = ItemActions.CopyObjects(menu_)
        copy_files.triggered.connect(lambda: CopyItem.set_is_cut(False))
        copy_files.triggered.connect(self.setup_urls_to_copy)
        menu_.addAction(copy_files)

        remove_files = ItemActions.RemoveObjects(menu_)
        remove_files.triggered.connect(lambda: self.remove_files(urls))
        menu_.addAction(remove_files)

    def context_grid(self, menu_: UMenu):

        def new_folder_start():
            self.rename_win = RenameWin("")
            self.rename_win.center(self.window())
            self.rename_win.finished_.connect(lambda name: new_folder_fin(name))
            self.rename_win.show()
        
        def new_folder_fin(name: str):
            dest = os.path.join(self.main_win_item.main_dir, name)
            try:
                os.mkdir(dest)
                self.new_thumb(dest)
            except Exception as e:
                Utils.print_error()

        self.path_bar_update_delayed(self.main_win_item.main_dir)
        names = [os.path.basename(self.main_win_item.main_dir)]
        urls = [self.main_win_item.main_dir]

        if CopyItem.urls and not self.is_grid_search:
            paste_files = GridActions.PasteObjects(menu_)
            paste_files.triggered.connect(self.paste_files)
            menu_.addAction(paste_files)

        menu_.addSeparator()

        if not self.is_grid_search and not Dynamic.rating_filter != 0:
            new_folder = GridActions.NewFolder(menu_)
            new_folder.triggered.connect(new_folder_start)
            menu_.addAction(new_folder)

        if not self.is_grid_search:
            info = GridActions.Info(menu_)
            info.triggered.connect(lambda: self.open_win_info(self.main_win_item.main_dir))
            menu_.addAction(info)

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

        reveal = GridActions.RevealInFinder(menu_, urls)
        menu_.addAction(reveal)

        copy_ = GridActions.CopyPath(menu_, urls)
        menu_.addAction(copy_)

        copy_name = GridActions.CopyName(menu_, names)
        menu_.addAction(copy_name)

        menu_.addSeparator()

        upd_ = GridActions.UpdateGrid(menu_)
        upd_.triggered.connect(lambda: self.load_st_grid.emit())
        menu_.addAction(upd_)

        change_view = GridActions.ChangeViewMenu(menu_, self.main_win_item.get_view_mode())
        change_view.triggered.connect(lambda: self.change_view.emit())
        menu_.addMenu(change_view)

        sort_menu = GridActions.SortMenu(menu_, self.sort_item)
        sort_menu.sort_grid_sig.connect(lambda: self.sort_thumbs())
        sort_menu.rearrange_grid_sig.connect(lambda: self.rearrange_thumbs())
        sort_menu.sort_menu_update.connect(lambda: self.sort_menu_update.emit())
        menu_.addMenu(sort_menu)

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.modifiers() & Qt.KeyboardModifier.ControlModifier:
            
            if a0.key() == Qt.Key.Key_X:
                CopyItem.set_is_cut(True)
                self.setup_urls_to_copy()

            if a0.key() == Qt.Key.Key_C:
                self.setup_urls_to_copy()

            elif a0.key() == Qt.Key.Key_V:
                if not self.is_grid_search:
                    self.paste_files()

            elif a0.key() == Qt.Key.Key_Up:
                self.level_up.emit()

            elif a0.key() == Qt.Key.Key_Down:
                # если есть выделенные виджеты, то берется url последнего из списка
                if self.selected_thumbs:
                    self.wid_under_mouse = self.selected_thumbs[-1]
                    if self.wid_under_mouse:
                        self.select_single_thumb(self.wid_under_mouse)
                        self.open_thumb()

            elif a0.key() == Qt.Key.Key_I:
                if self.selected_thumbs:
                    self.wid_under_mouse = self.selected_thumbs[-1]
                    self.select_single_thumb(self.wid_under_mouse)
                    self.open_win_info(self.wid_under_mouse.src)
                else:
                    self.open_win_info(self.main_win_item.main_dir)

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
                    self.select_multiple_thumb(wid)

            elif a0.key() == Qt.Key.Key_Backspace:
                urls = [i.src for i in self.selected_thumbs]
                self.remove_files(urls)

        elif a0.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return):
            if self.selected_thumbs:
                self.wid_under_mouse = self.selected_thumbs[-1]
                if self.wid_under_mouse:
                    self.open_thumb()

        elif a0.key() in KEY_NAVI:
            offset = KEY_NAVI.get(a0.key())

            if not self.cell_to_wid:
                return

            if not self.selected_thumbs:
                self.wid_under_mouse = self.cell_to_wid.get((0, 0))
                if len(self.url_to_wid.values()) == 1:
                    self.select_single_thumb(self.wid_under_mouse)
                    return
            else:
                self.wid_under_mouse = self.selected_thumbs[-1]
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
                self.select_single_thumb(next_wid)
                self.ensureWidgetVisible(next_wid)
                self.wid_under_mouse = next_wid
        elif a0.key() in KEY_RATING:
            rating = KEY_RATING.get(a0.key())
            self.new_rating_multiple_start(rating)

        self.total_count_update.emit((len(self.selected_thumbs), len(self.cell_to_wid)))
        return super().keyPressEvent(a0)

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:
        menu_ = UMenu(parent=self)
        self.wid_under_mouse = self.get_wid_under_mouse(a0)
        # клик по пустому пространству
        if not self.wid_under_mouse:
            self.clear_selected_widgets()
            self.context_grid(menu_)

        # клик по виджету
        else:
            # если не было выделено ни одного виджет ранее
            # то выделяем кликнутый
            if not self.selected_thumbs:
                self.select_multiple_thumb(self.wid_under_mouse)
            # если есть выделенные виджеты, но кликнутый виджет не выделены
            # то снимаем выделение с других и выделяем кликнутый
            elif self.wid_under_mouse not in self.selected_thumbs:
                self.clear_selected_widgets()
                self.select_multiple_thumb(self.wid_under_mouse)
            
            if isinstance(self.wid_under_mouse, (BaseItem, Thumb)):
                self.context_thumb(menu_, self.wid_under_mouse)
            else:
                self.context_grid(menu_)

        self.total_count_update.emit((len(self.selected_thumbs), len(self.cell_to_wid)))
        menu_.show_under_cursor()
    
    def dragEnterEvent(self, a0):
        if self.is_grid_search:
            return
        if a0.mimeData().hasUrls():
            a0.acceptProposedAction()
        return super().dragEnterEvent(a0)
    
    def dropEvent(self, a0):
        if not a0.mimeData().urls():
            return
        sys_vol = EvloshUtils.get_sys_vol()
        urls = [
            EvloshUtils.norm_slash(i.toLocalFile())
            for i in a0.mimeData().urls()
        ]
        urls = [
            EvloshUtils.add_sys_vol(i, sys_vol)
            for i in urls
        ]
        src = os.path.dirname(urls[0])
        is_cut = src.split(os.sep)[:3] == self.main_win_item.main_dir.split(os.sep)[:3]
        if self.is_grid_search:
            is_cut = False
        print(self.is_grid_search)
        return

        if src == self.main_win_item.main_dir:
            print("нельзя копировать в себя через DropEvent")
            return
        else:
            CopyItem.set_is_cut(is_cut)
            CopyItem.set_src(src)
            CopyItem.urls = urls
            self.paste_files()
        return super().dropEvent(a0)

    def deleteLater(self):
        for i in self.load_images_tasks:
            i.set_should_run(False)
        return super().deleteLater()
    
    def closeEvent(self, a0):
        for i in self.load_images_tasks:
            i.set_should_run(False)
        return super().closeEvent(a0)