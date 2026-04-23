import os

from PyQt5.QtCore import (QMimeData, QPoint, QRect, QSize, Qt, QTimer, QUrl,
                          pyqtSignal)
from PyQt5.QtGui import (QContextMenuEvent, QDrag, QImage, QKeyEvent,
                         QMouseEvent, QPixmap)
from PyQt5.QtWidgets import (QApplication, QFrame, QGraphicsOpacityEffect,
                             QGridLayout, QLabel, QRubberBand, QVBoxLayout,
                             QWidget)

from cfg import Dynamic, JsonData, Static
from system.items import (ClipboardItemGlob, DataItem, ImgViewItem,
                          MainWinItem, SortItem, TotalCountItem)
from system.shared_utils import ImgUtils, SharedUtils
from system.utils import Utils

from ._base_widgets import UMenu, UScrollArea
from .actions import GridActions, ItemActions
# в main win
from .win_img_convert import WinImgConvert
from .win_remove_files import WinRemoveFiles
from .win_rename import WinRename

FONT_SIZE = 11
BORDER_RADIUS = 4

KEY_NAVI = {
    Qt.Key.Key_Left: (0, -1),
    Qt.Key.Key_Right: (0, 1),
    Qt.Key.Key_Up: (-1, 0),
    Qt.Key.Key_Down: (1, 0)
}


class ImgFrameWidget(QFrame):
    def __init__(self):
        super().__init__()


class WhiteTextWid(QLabel):
    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(f"""font-size: {FONT_SIZE}px;""")

    def set_text(self, data: DataItem) -> list[str]:
        name: str | list = data.filename
        max_row = Static.row_limits[Dynamic.pixmap_size_ind]
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


class BlueTextWid(QLabel):

    def __init__(self):
        super().__init__()
        self.blue_color = "#6199E4"
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            f"""
            font-size: {FONT_SIZE}px;
            color: {self.blue_color};
            """
        )
    
    def set_text(self, data_item: DataItem, sort_item: SortItem):
        if sort_item.item_type == sort_item.mod:
            row = f"Изм: {SharedUtils.get_f_date(data_item.mod)}"
        elif sort_item.item_type == sort_item.added:
            row = f"Доб: {SharedUtils.get_f_date(data_item.added)}"
        elif sort_item.item_type == sort_item.type_:
            row = f"Тип: {data_item.type_}"
        elif sort_item.item_type == sort_item.size:
            if data_item.type_ == Static.folder_type:
                row = ""
            else:
                row = f"Размер: {SharedUtils.get_f_size(data_item.size)}"
        elif sort_item.item_type == sort_item.filename:
            if data_item.type_ == Static.folder_type:
                row = ""
            else:
                row = (
                    f"Изм: {SharedUtils.get_f_date(data_item.mod)}\n"
                    f"Размер: {SharedUtils.get_f_size(data_item.size)}"
                )
        self.setText(row)


class Thumb(QFrame):
    # Сигнал нужен, чтобы менялся заголовок в просмотрщике изображений
    # При изменении рейтинга или меток
    text_changed = pyqtSignal()
    img_obj_name: str = "img_frame"
    text_obj_name: str = "text_frame_"

    current_image_size: int = 0
    current_img_frame_size: int = 0
    thumb_w: int = 0
    thumb_h: int = 0
    corner: int = 0
    image_icons: dict[int, QPixmap] = {}
    folder_icons: dict[int, QPixmap] = {}
    disk_icons: dict[int, QPixmap] = {}

    def __init__(self, data_item: DataItem):
        super().__init__()
        self.data_item = data_item

        self.v_lay = QVBoxLayout()
        self.v_lay.setContentsMargins(0, 0, 0, 0)
        self.v_lay.setSpacing(2)
        self.v_lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setLayout(self.v_lay)

        self.img_frame = ImgFrameWidget()
        self.img_frame.setObjectName(Thumb.img_obj_name)
        self.v_lay.addWidget(self.img_frame, alignment=Qt.AlignmentFlag.AlignCenter)

        self.img_frame_lay = QVBoxLayout()
        self.img_frame_lay.setContentsMargins(0, 0, 0, 0)
        self.img_frame_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_frame.setLayout(self.img_frame_lay)

        self.img_wid = QLabel()
        self.img_wid.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_frame_lay.addWidget(self.img_wid)

        self.white_text_wid = WhiteTextWid()
        self.white_text_wid.setObjectName(Thumb.text_obj_name)
        self.v_lay.addWidget(self.white_text_wid, alignment=Qt.AlignmentFlag.AlignCenter)

        self.blue_text_wid = BlueTextWid()
        self.v_lay.addWidget(self.blue_text_wid, alignment=Qt.AlignmentFlag.AlignCenter)
    
    @classmethod
    def calc_size(cls):
        ind = Dynamic.pixmap_size_ind
        Thumb.current_image_size = Static.image_sizes[ind]
        Thumb.current_img_frame_size = Thumb.current_image_size + 15
        Thumb.thumb_w = Static.thumb_widths[ind]
        Thumb.thumb_h = Static.thumb_heights[ind]
        Thumb.corner = Static.corner_sizes[ind]

    @classmethod
    def setup_icons(cls):
        folder_icon = QImage(
            os.path.join(Static.internal_images_dir, "folder.png")
        )
        image_icon = QImage(
            os.path.join(Static.internal_images_dir, "image.png")
        )
        disk_icon = QImage(
            os.path.join(Static.internal_images_dir, "disk.png")
        )

        for i in Static.image_sizes:
            resized_folder = Utils.scaled(folder_icon, i)
            resized_image = Utils.scaled(image_icon, i)
            resized_disk = Utils.scaled(disk_icon, i)
            cls.folder_icons[i] = QPixmap.fromImage(resized_folder)
            cls.image_icons[i] = QPixmap.fromImage(resized_image)
            cls.disk_icons[i] = QPixmap.fromImage(resized_disk)

    def set_icon(self):
        if self.data_item.abs_path.endswith(ImgUtils.ext_all):
            icons = Thumb.image_icons
        elif (
            self.data_item.abs_path.count(os.sep) == 2
            and
            self.data_item.abs_path.startswith("/Volumes")
        ):
            icons = Thumb.disk_icons
        else:
            icons = Thumb.folder_icons
        self.img_wid.setPixmap(icons[Thumb.current_image_size])

    def set_image(self):
        qimage = self.data_item.qimages[Thumb.current_image_size]
        pixmap = QPixmap.fromImage(qimage)
        self.img_wid.setPixmap(pixmap)

    def update_all(self, sort_item: SortItem):
        self.white_text_wid.set_text(self.data_item)
        self.blue_text_wid.set_text(self.data_item, sort_item)

        if self.width() == Thumb.thumb_w:
            return

        self.setFixedSize(
            Thumb.thumb_w,
            Thumb.thumb_h
        )
        self.img_wid.setFixedSize(
            Thumb.current_image_size,
            Thumb.current_image_size
        )
        self.img_frame.setFixedSize(
            Thumb.current_img_frame_size,
            Thumb.current_img_frame_size
        )

        if self.data_item.qimages:
            self.set_image()
        else:
            self.set_icon()

    def set_frame(self):
        self.data_item.is_selected = True
        self.setStyleSheet(
            f"""
            #{Thumb.text_obj_name} {{
                background: {Static.rgba_blue};
                font-size: {FONT_SIZE}px;
                border-radius: {BORDER_RADIUS}px;
                padding: 2px;
            }}
            #{Thumb.img_obj_name} {{
                background: {Static.rgba_gray};
                font-size: {FONT_SIZE}px;
                border-radius: {Thumb.corner}px;
            }}
            """
        )

    def set_no_frame(self):
        self.data_item.is_selected = False
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
                border-radius: {Thumb.corner}px;
            }}
            """
        )

    def set_transparent_frame(self, value: float):
        effect = QGraphicsOpacityEffect(self)
        effect.setOpacity(value)
        self.setGraphicsEffect(effect)


class NoItemsLabel(QLabel):
    no_files = "Нет изображений"
    no_filter = "Нет файлов с выбранным рейтингом или фильтром."
    def __init__(self, text: str):
        super().__init__(text)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)


class Grid(UScrollArea):
    new_folder_text = "Новая папка"

    new_history_item = pyqtSignal(str)
    path_bar_update = pyqtSignal(str)
    add_fav = pyqtSignal(str)
    del_fav = pyqtSignal(str)
    load_st_grid = pyqtSignal(str)
    move_slider = pyqtSignal(int)
    change_view = pyqtSignal()
    new_main_win_open = pyqtSignal(str)
    go_to_widget = pyqtSignal(str)
    level_up = pyqtSignal()
    menu_sort_update = pyqtSignal()
    total_count_update = pyqtSignal(TotalCountItem)
    open_win_info = pyqtSignal(list)
    img_view_win = pyqtSignal(ImgViewItem)
    paste_files = pyqtSignal()
    load_finished = pyqtSignal()
    files_icon = Utils.scaled(
        qimage=QImage(os.path.join(Static.internal_images_dir, "files.png")),
        size=64
    )

    def __init__(self, main_win_item: MainWinItem, is_grid_search: bool):
        super().__init__()
        self.setWidgetResizable(True)
        self.horizontalScrollBar().setDisabled(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.is_grid_search: bool = is_grid_search
        self.main_win_item: MainWinItem = main_win_item
        self.sort_item: SortItem = 1
        self.col_count: int = 0
        self.row: int = 0
        self.col: int = 0
        self.url_to_wid: dict[str, Thumb] = {}
        self.cell_to_wid: dict[tuple, Thumb] = {}
        self.selected_thumbs: list[Thumb] = []
        self.wid_under_mouse: Thumb = None
        self.loaded_thumbs: list[Thumb] = []
        self.ignore_mouse = False

        self.grid_wid = QWidget()
        self.setWidget(self.grid_wid)
        self.origin_pos = QPoint()
        self.rubberBand = QRubberBand(QRubberBand.Rectangle, self.grid_wid)

        self.grid_layout = QGridLayout()
        self.grid_wid.setLayout(self.grid_layout)
        self.grid_layout.setSpacing(5)
        self.grid_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )

    def reload_rubber(self):
        self.rubberBand.deleteLater()
        self.rubberBand = QRubberBand(QRubberBand.Rectangle, self.grid_wid)
    
    def get_clmn_count(self):
        try:
            return self.viewport().width() // Thumb.thumb_w
        except ZeroDivisionError:
            return 1

    def bar_path_update(self, src: str):
        QTimer.singleShot(0, lambda: self.path_bar_update.emit(src))
    
    def sort_thumbs(self):
        data_items = [i.data_item for i in self.url_to_wid.values()]
        sorted_data_items = DataItem.sort_(data_items, self.sort_item)
        new_url_to_wid = {}
        for i in sorted_data_items:
            wid = self.url_to_wid.get(i.abs_path)
            new_url_to_wid[i.abs_path] = wid
            wid.update_all(self.sort_item)
        self.url_to_wid = new_url_to_wid
                
    def filter_thumbs(self):
        visible_thumbs = 0
        for wid in self.url_to_wid.values():
            show_widget = True
            if Dynamic.word_filters:
                for i in Dynamic.word_filters:
                    if i.lower() not in wid.data_item.filename.lower():
                        show_widget = False
            if show_widget:
                wid.data_item.must_hidden = False
                wid.show()
                visible_thumbs += 1
            else:
                wid.data_item.must_hidden = True
                wid.hide()
        if visible_thumbs == 0:
            self.no_items_label_remove()
            self.no_items_label_create(NoItemsLabel.no_filter)
        else:
            self.no_items_label_remove()

    def resize_thumbs(self):
        Thumb.calc_size()
        for wid in self.url_to_wid.values():
            wid.update_all(self.sort_item)
        for i in self.selected_thumbs:
            i.set_frame()

    def rearrange_thumbs(self):
        self.cell_to_wid.clear()
        self.row, self.col = 0, 0
        self.col_count = self.get_clmn_count()
        for wid in self.url_to_wid.values():
            if wid.data_item.must_hidden:
                continue
            self.grid_layout.addWidget(wid, self.row, self.col)
            self.add_widget_data(wid, self.row, self.col)
            self.col += 1
            if self.col >= self.col_count:
                self.col = 0
                self.row += 1
        item = TotalCountItem(
            selected=len(self.selected_thumbs),
            total=len(self.cell_to_wid)
        )
        self.total_count_update.emit(item)

    def add_widget_data(self, wid: Thumb, row: int, col: int):
        wid.data_item.row, wid.data_item.col = row, col
        self.cell_to_wid[row, col] = wid
        self.url_to_wid[wid.data_item.abs_path] = wid

    def open_thumb(self):
        if len(self.selected_thumbs) == 1:
            wid = self.selected_thumbs[0]
            if wid.data_item.type_ == Static.folder_type:
                self.new_history_item.emit(wid.data_item.abs_path)
                self.load_st_grid.emit(wid.data_item.abs_path)
            else:
                url_to_wid = {
                    url: wid
                    for url, wid in self.url_to_wid.items()
                    if url.endswith(ImgUtils.ext_all)
                    and
                    not wid.data_item.must_hidden
                }
                if url_to_wid:
                    item = ImgViewItem(
                        start_url=wid.data_item.abs_path,
                        url_to_wid=url_to_wid,
                        is_selection=False
                    )
                    self.img_view_win.emit(item)
        else:
            img_widgets = [
                wid
                for wid in self.selected_thumbs
                if wid.data_item.type_.endswith(ImgUtils.ext_all)
                and
                not wid.data_item.must_hidden
            ]
            url_to_wid = {
                wid.data_item.abs_path: wid
                for wid in img_widgets
            }
            if img_widgets:

                wid = img_widgets[-1]
                item = ImgViewItem(
                    start_url=wid.data_item.abs_path,
                    url_to_wid=url_to_wid,
                    is_selection=True
                )
                self.img_view_win.emit(item)


    def fav_cmd(self, offset: int, src: str):
        (self.add_fav if offset == 1 else self.del_fav).emit(src)

    def show_in_folder_cmd(self, wid: Thumb):
        QTimer.singleShot(
            100,
            lambda: self.go_to_widget.emit(wid.data_item.abs_path)
        )

    def setup_urls_to_copy(self):
        ClipboardItemGlob.src_dir = self.main_win_item.abs_current_dir
        ClipboardItemGlob.is_search = self.is_grid_search
        ClipboardItemGlob.src_urls.clear()
        for i in self.selected_thumbs:
            ClipboardItemGlob.src_urls.append(i.data_item.abs_path)

    def no_items_label_remove(self):
        wid = self.grid_wid.findChild(NoItemsLabel)
        if wid:
            wid.deleteLater()
            flags = Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
            self.grid_layout.setAlignment(flags)
            try:
                del self.mouseMoveEvent
            except AttributeError:
                ...

    def no_items_label_create(self, text: str):
        no_images = NoItemsLabel(text)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.grid_layout.addWidget(no_images, 0, 0)

    def remove_files(self, urls: list[str]):
        self.rem_win = WinRemoveFiles(self.main_win_item, urls)
        self.rem_win.center(self.window())
        self.rem_win.show()
        
    def clear_selected_widgets(self):
        """
        Очищает список выделенных виджетов и снимает визуальное выделение с них
        """
        for i in self.selected_thumbs:
            i.set_no_frame()
        self.selected_thumbs.clear()

    def select_single_thumb(self, wid: DataItem | Thumb):
        """
        Очищает визуальное выделение с выделенных виджетов и очищает список.  
        Выделяет виджет, добавляет его в список выделенных виджетов.
        """
        if isinstance(wid, Thumb):
            self.bar_path_update(wid.data_item.abs_path)
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
        TextWidget, ImgFrame     
        QLabel и QSvgWidget являются дочерними виджетами ImgFrame, поэтому  
        в случае клика по ним, возвращается .parent().parent()
        """
        wid = QApplication.widgetAt(a0.globalPos())

        if isinstance(wid, (WhiteTextWid, BlueTextWid, ImgFrameWidget)):
            return wid.parent()
        elif isinstance(wid, QLabel):
            return wid.parent().parent()
        else:
            return None

    def open_img_convert_win(self, urls: list[str]):
        self.convert_win = WinImgConvert(urls)
        self.convert_win.center(self.window())
        self.convert_win.show()

    def set_transparent_thumbs(self):
        for i in self.selected_thumbs:
            i.set_transparent_frame(0.5)

    def rename_thumb(self, thumb: Thumb):
        
        def finished(text: str):
            root = os.path.dirname(thumb.data_item.abs_path)
            new_url = os.path.join(root, text)
            os.rename(thumb.data_item.abs_path, new_url)
            thumb.update_all(self.sort_item)

        self.rename_win = WinRename(thumb.data_item.filename)
        self.rename_win.finished_.connect(lambda text: finished(text))
        self.rename_win.center(self.window())
        self.rename_win.show()

    def context_thumb(self, menu_: UMenu, wid: Thumb):
        # собираем пути к файлам / папкам у выделенных виджетов
        urls = [
            i.data_item.abs_path
            for i in self.selected_thumbs
        ]
        urls_img = [
            i.data_item.abs_path
            for i in self.selected_thumbs
            if i.data_item.abs_path.endswith(ImgUtils.ext_all)
        ]
        dirs = [
            i.data_item.abs_path
            for i in self.selected_thumbs
            if i.data_item.type_ == Static.folder_type
        ]
        self.bar_path_update(wid.data_item.abs_path)

        menu_.setMinimumWidth(215)

        view_action = ItemActions.OpenThumb(menu_)
        view_action.triggered.connect(lambda: self.open_thumb())
        menu_.addAction(view_action)

        if wid.data_item.type_ in ImgUtils.ext_all:
            open_in_app = ItemActions.OpenInApp(menu_, urls)
            menu_.addMenu(open_in_app)

        elif wid.data_item.type_ == Static.folder_type:
            new_win = ItemActions.OpenInNewWindow(menu_)
            new_win.triggered.connect(
                lambda: self.new_main_win_open.emit(wid.data_item.abs_path)
            )
            menu_.addAction(new_win)

            if wid.data_item.abs_path in JsonData.favs:
                cmd_ = lambda: self.fav_cmd(offset=-1, src=wid.data_item.abs_path)
                fav_action = ItemActions.FavRemove(menu_)
                fav_action.triggered.connect(cmd_)
                menu_.addAction(fav_action)
            else:
                cmd_ = lambda: self.fav_cmd(offset=1, src=wid.data_item.abs_path)
                fav_action = ItemActions.FavAdd(menu_)
                fav_action.triggered.connect(cmd_)
                menu_.addAction(fav_action)

        info = ItemActions.Info(menu_)
        info.triggered.connect(
            lambda: self.open_win_info.emit(
                [i.data_item for i in self.selected_thumbs]
            )
        )
        menu_.addAction(info)

        menu_.addSeparator()

        if wid.data_item.type_ in ImgUtils.ext_all and not self.is_grid_search:
            convert_action = ItemActions.ImgConvert(menu_)
            convert_action.triggered.connect(lambda: self.open_img_convert_win(urls_img))
            menu_.addAction(convert_action)

        menu_.addSeparator()

        # is grid search устанавливается на True при инициации GridSearch
        if self.is_grid_search:
            show_in_folder = ItemActions.ShowInGrid(menu_)
            cmd_ = lambda: self.show_in_folder_cmd(wid)
            show_in_folder.triggered.connect(cmd_)
            menu_.addAction(show_in_folder)

        show_in_finder_action = ItemActions.RevealInFinder(menu_, urls)
        menu_.addAction(show_in_finder_action)

        copy_path = ItemActions.CopyPath(menu_, urls)
        copy_path.triggered.connect(lambda: ClipboardItemGlob.reset())
        menu_.addAction(copy_path)


        menu_.addSeparator()

        rename = ItemActions.Rename(menu_)
        rename.triggered.connect(lambda: self.rename_thumb(wid))
        menu_.addAction(rename)

        cut_objects = ItemActions.CutObjects(menu_)
        cut_objects.triggered.connect(self.set_transparent_thumbs)
        cut_objects.triggered.connect(lambda: ClipboardItemGlob.set_is_cut(True))
        cut_objects.triggered.connect(self.setup_urls_to_copy)
        menu_.addAction(cut_objects)

        copy_files = ItemActions.CopyObjects(menu_)
        copy_files.triggered.connect(lambda: ClipboardItemGlob.set_is_cut(False))
        copy_files.triggered.connect(self.setup_urls_to_copy)
        menu_.addAction(copy_files)

        if not self.is_grid_search:
            remove_files = ItemActions.RemoveObjects(menu_)
            remove_files.triggered.connect(lambda: self.remove_files(urls))
            menu_.addAction(remove_files)

    def context_grid(self, menu_: UMenu):
        self.bar_path_update(self.main_win_item.abs_current_dir)
        names = [os.path.basename(self.main_win_item.abs_current_dir)]
        urls = [self.main_win_item.abs_current_dir]
        item = DataItem(self.main_win_item.abs_current_dir)
        item.set_properties()

        if not self.is_grid_search:
            new_folder = GridActions.NewFolder(menu_)
            new_folder.triggered.connect(self.new_folder)
            menu_.addAction(new_folder)

        if not self.is_grid_search:
            info = GridActions.Info(menu_)
            info.triggered.connect(lambda: self.open_win_info.emit([item, ]))
            menu_.addAction(info)

        if self.main_win_item.abs_current_dir in JsonData.favs:
            cmd_ = lambda: self.fav_cmd(-1, self.main_win_item.abs_current_dir)
            fav_action = GridActions.FavRemove(menu_)
            fav_action.triggered.connect(cmd_)
            menu_.addAction(fav_action)

        else:
            cmd_ = lambda: self.fav_cmd(+1, self.main_win_item.abs_current_dir)
            fav_action = GridActions.FavAdd(menu_)
            fav_action.triggered.connect(cmd_)
            menu_.addAction(fav_action)

        menu_.addSeparator()

        reveal = GridActions.RevealInFinder(menu_, urls)
        menu_.addAction(reveal)

        copy_ = GridActions.CopyPath(menu_, urls)
        copy_.triggered.connect(ClipboardItemGlob.reset)
        menu_.addAction(copy_)

        copy_name = GridActions.CopyName(menu_, names)
        copy_name.triggered.connect(ClipboardItemGlob.reset)
        menu_.addAction(copy_name)

        menu_.addSeparator()

        if ClipboardItemGlob.src_urls and not self.is_grid_search:
            paste_files = GridActions.PasteObjects(menu_)
            paste_files.triggered.connect(self.paste_files.emit)
            menu_.addAction(paste_files)

            menu_.addSeparator()

        upd_ = GridActions.UpdateGrid(menu_)
        upd_.triggered.connect(lambda: self.load_st_grid.emit(self.main_win_item.abs_current_dir))
        menu_.addAction(upd_)

        change_view = GridActions.ChangeViewMenu(menu_, self.main_win_item.get_view_mode())
        change_view.triggered.connect(lambda: self.change_view.emit())
        menu_.addMenu(change_view)

        sort_menu = GridActions.SortMenu(menu_, self.sort_item)
        sort_menu.sort_grid_sig.connect(lambda: self.sort_thumbs())
        sort_menu.rearrange_grid_sig.connect(lambda: self.rearrange_thumbs())
        sort_menu.sort_menu_update.connect(lambda: self.menu_sort_update.emit())
        menu_.addMenu(sort_menu)

    def mouseReleaseEvent(self, a0: QMouseEvent):
        if a0.button() != Qt.MouseButton.LeftButton:
            return
        
        elif self.rubberBand.isVisible():
            release_pos = self.grid_wid.mapFrom(self, a0.pos())
            rect = QRect(self.origin_pos, release_pos).normalized()
            self.rubberBand.hide()
            ctrl = a0.modifiers() in (Qt.KeyboardModifier.ControlModifier, Qt.KeyboardModifier.ShiftModifier)
            for wid in self.cell_to_wid.values():
                intersects = False
                inner_widgets = wid.findChildren((WhiteTextWid, ImgFrameWidget))
                for w in inner_widgets:
                    top_left = w.mapTo(self.grid_wid, QPoint(0, 0))
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
            self.bar_path_update(self.main_win_item.abs_current_dir)
        
        elif a0.modifiers() == Qt.KeyboardModifier.ShiftModifier:
            # шифт клик: если не было выделенных виджетов
            if not self.selected_thumbs:
                self.select_multiple_thumb(self.wid_under_mouse)
            # шифт клик: если уже был выделен один / несколько виджетов
            else:
                coords = list(self.cell_to_wid)
                start_pos = (self.selected_thumbs[-1].data_item.row, self.selected_thumbs[-1].data_item.col)
                # шифт клик: слева направо (по возрастанию)
                if coords.index((self.wid_under_mouse.data_item.row, self.wid_under_mouse.data_item.col)) > coords.index(start_pos):
                    start = coords.index(start_pos)
                    end = coords.index((self.wid_under_mouse.data_item.row, self.wid_under_mouse.data_item.col))
                    coords = coords[start : end + 1]
                # шифт клик: справа налево (по убыванию)
                else:
                    start = coords.index((self.wid_under_mouse.data_item.row, self.wid_under_mouse.data_item.col))
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
                self.bar_path_update(self.wid_under_mouse.data_item.abs_path)
        else:
            self.select_single_thumb(self.wid_under_mouse)

        item = TotalCountItem(
            selected=len(self.selected_thumbs),
            total=len(self.cell_to_wid)
        )
        self.total_count_update.emit(item)

    def mouseDoubleClickEvent(self, a0):
        if self.wid_under_mouse:
            self.select_single_thumb(self.wid_under_mouse)
            self.open_thumb()

    def mousePressEvent(self, a0):
        if a0.button() == Qt.MouseButton.LeftButton:
            self.origin_pos = self.grid_wid.mapFrom(self, a0.pos())
            self.wid_under_mouse = self.get_wid_under_mouse(a0)
        return super().mousePressEvent(a0)

    def mouseMoveEvent(self, a0):
        if self.ignore_mouse:
            return
        try:
            current_pos = self.grid_wid.mapFrom(self, a0.pos())
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
        self.drag = QDrag(self)
        self.mime_data = QMimeData()
        img_ = QPixmap.fromImage(self.files_icon)
        self.drag.setPixmap(img_)
        urls = [QUrl.fromLocalFile(i.data_item.abs_path) for i in self.selected_thumbs]        
        if urls:
            self.mime_data.setUrls(urls)
        if self.wid_under_mouse:
            self.bar_path_update(self.wid_under_mouse.data_item.abs_path)
        item = TotalCountItem(
            selected=len(self.selected_thumbs),
            total=len(self.cell_to_wid)
        )
        self.total_count_update.emit(item)
        self.drag.setMimeData(self.mime_data)
        self.setup_urls_to_copy()
        self.drag.exec_(Qt.DropAction.CopyAction)
        return super().mouseMoveEvent(a0)

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.modifiers() & Qt.KeyboardModifier.ControlModifier:
            
            if a0.key() == Qt.Key.Key_X:
                self.set_transparent_thumbs()
                ClipboardItemGlob.set_is_cut(True)
                self.setup_urls_to_copy()

            if a0.key() == Qt.Key.Key_C:
                ClipboardItemGlob.set_is_cut(False)
                self.setup_urls_to_copy()

            elif a0.key() == Qt.Key.Key_V:
                if ClipboardItemGlob.src_urls and not self.is_grid_search:
                    self.paste_files.emit()

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
                    self.open_win_info.emit(
                        [i.data_item for i in self.selected_thumbs]
                    )
                else:
                    data = DataItem(self.main_win_item.abs_current_dir)
                    data.set_properties()
                    self.open_win_info.emit([data, ])

            elif a0.key() == Qt.Key.Key_Equal:
                new_value = Dynamic.pixmap_size_ind + 1
                if new_value <= len(Static.image_sizes) - 1:
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
                urls = [i.data_item.abs_path for i in self.selected_thumbs]
                self.remove_files(urls)

        elif a0.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return):
            if self.selected_thumbs:
                self.wid_under_mouse = self.selected_thumbs[-1]
                if self.wid_under_mouse:
                    if not a0.isAutoRepeat():
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
                self.wid_under_mouse.data_item.row + offset[0], 
                self.wid_under_mouse.data_item.col + offset[1]
            )
            next_wid = self.cell_to_wid.get(coords)
            if next_wid is None:
                if a0.key() == Qt.Key.Key_Right:
                    coords = (
                        self.wid_under_mouse.data_item.row + 1, 
                        0
                    )
                elif a0.key() == Qt.Key.Key_Left:
                    coords = (
                        self.wid_under_mouse.data_item.row - 1,
                        self.col_count - 1
                    )
                next_wid = self.cell_to_wid.get(coords)
            if next_wid:
                self.select_single_thumb(next_wid)
                self.ensureWidgetVisible(next_wid)
                self.wid_under_mouse = next_wid

        item = TotalCountItem(
            selected=len(self.selected_thumbs),
            total=len(self.cell_to_wid)
        )
        self.total_count_update.emit(item)
        return super().keyPressEvent(a0)

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:
        if self.ignore_mouse:
            return
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
            
            if isinstance(self.wid_under_mouse, (DataItem, Thumb)):
                self.context_thumb(menu_, self.wid_under_mouse)
            else:
                self.context_grid(menu_)

        item = TotalCountItem(
            selected=len(self.selected_thumbs),
            total=len(self.cell_to_wid)
        )
        self.total_count_update.emit(item)
        menu_.show_under_cursor()
    
    def deleteLater(self):
        urls = [i.data_item.abs_path for i in self.selected_thumbs]
        self.main_win_item.urls_to_select = urls
        return super().deleteLater()
    
    def closeEvent(self, a0):
        urls = [i.src for i in self.selected_thumbs]
        self.main_win_item.urls_to_select = urls
        return super().closeEvent(a0)
