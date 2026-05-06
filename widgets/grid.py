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
                          MainWinItem, NameUrlItem, SortItem, TotalCountItem)
from system.shared_utils import ImgUtils, SharedUtils
from system.utils import Utils

from ._base_widgets import UMenu, UScrollArea, BaseSignals
from .actions import Actions, Menus

FONT_SIZE = 11
BORDER_RADIUS = 4

KEY_NAVI = {
    Qt.Key.Key_Left: (0, -1),
    Qt.Key.Key_Right: (0, 1),
    Qt.Key.Key_Up: (-1, 0),
    Qt.Key.Key_Down: (1, 0)
}


class ThumbImgWidget(QLabel):
    offset = 5
    corner_value = 10
    corners: list[int] = []
    image_icons: dict[int, QPixmap] = {}
    folder_icons: dict[int, QPixmap] = {}
    disk_icons: dict[int, QPixmap] = {}
    def __init__(self):
        super().__init__()
        self.setContentsMargins(self.offset, self.offset, self.offset, self.offset)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_no_frame_style()

    @classmethod
    def create_icons(cls):
        images = Static.internal_images_dir
        folder_icon = QImage(os.path.join(images, "folder.png"))
        image_icon = QImage(os.path.join(images, "image.png"))
        disk_icon = QImage(os.path.join(images, "disk.png"))
        for i in Static.image_sizes:
            resized_folder = Utils.scaled(folder_icon, i - cls.offset)
            resized_image = Utils.scaled(image_icon, i - cls.offset)
            resized_disk = Utils.scaled(disk_icon, i - cls.offset)
            cls.folder_icons[i] = QPixmap.fromImage(resized_folder)
            cls.image_icons[i] = QPixmap.fromImage(resized_image)
            cls.disk_icons[i] = QPixmap.fromImage(resized_disk)
            cls.corners.append(int(i // cls.corner_value))

    def set_framed_style(self):
        corner = self.corners[Dynamic.pixmap_size_ind]
        self.setStyleSheet(
            f"""
                background: {Static.rgba_gray};
                font-size: {FONT_SIZE}px;
                border-radius: {corner}px;
            """
        )

    def set_no_frame_style(self):
        corner = self.corners[Dynamic.pixmap_size_ind]
        self.setStyleSheet(
            f"""
                background: transparent;
                font-size: {FONT_SIZE}px;
                border-radius: {corner}px;
            """
        )
    

class WhiteTextWid(QLabel):
    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_no_frame_style()

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
    
    def set_framed_style(self):
        self.setStyleSheet(
            f"""
                background: {Static.rgba_blue};
                font-size: {FONT_SIZE}px;
                border-radius: {BORDER_RADIUS}px;
                padding: 2px;
            """
        )

    def set_no_frame_style(self):
        self.setStyleSheet(
            f"""
                background: transparent;
                font-size: {FONT_SIZE}px;
                border-radius: {BORDER_RADIUS}px;
                padding: 2px;
            """
        )


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
    pixmap_size: int = 0
    thumb_width: int = 0
    thumb_height: int = 0

    def __init__(self, data_item: DataItem):
        super().__init__()
        self.data_item = data_item

        self.v_lay = QVBoxLayout(self)
        self.v_lay.setContentsMargins(0, 0, 0, 0)
        self.v_lay.setSpacing(3)
        self.v_lay.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.img_wid = ThumbImgWidget()
        self.v_lay.addWidget(self.img_wid, alignment=Qt.AlignmentFlag.AlignCenter)

        self.white_text_wid = WhiteTextWid()
        self.v_lay.addWidget(self.white_text_wid, alignment=Qt.AlignmentFlag.AlignCenter)

        self.blue_text_wid = BlueTextWid()
        self.v_lay.addWidget(self.blue_text_wid, alignment=Qt.AlignmentFlag.AlignCenter)
    
    @classmethod
    def calc_size(cls):
        ind = Dynamic.pixmap_size_ind
        Thumb.pixmap_size = Static.image_sizes[ind]
        Thumb.thumb_width = Static.thumb_widths[ind]
        Thumb.thumb_height = Static.thumb_heights[ind]

    @classmethod
    def create_icons(cls):
        ThumbImgWidget.create_icons()

    def set_icon(self):
        if self.data_item.abs_path.endswith(ImgUtils.ext_all):
            icons = ThumbImgWidget.image_icons
        elif (
            self.data_item.abs_path.count(os.sep) == 2
            and
            self.data_item.abs_path.startswith("/Volumes")
        ):
            icons = ThumbImgWidget.disk_icons
        else:
            icons = ThumbImgWidget.folder_icons
        self.img_wid.setPixmap(icons[Thumb.pixmap_size])

    def set_image(self):
        qimage = self.data_item.qimages[Thumb.pixmap_size]
        pixmap = QPixmap.fromImage(qimage)
        self.img_wid.setPixmap(pixmap)

    def update_all(self, sort_item: SortItem):
        self.white_text_wid.set_text(self.data_item)
        self.blue_text_wid.set_text(self.data_item, sort_item)

        if self.width() == Thumb.thumb_width:
            return

        self.setFixedSize(
            Thumb.thumb_width,
            Thumb.thumb_height
        )
        self.img_wid.setFixedSize(
            Thumb.pixmap_size,
            Thumb.pixmap_size
        )
        if self.data_item.qimages:
            self.set_image()
        else:
            self.set_icon()

    def set_frame(self):
        self.data_item.is_selected = True
        self.white_text_wid.set_framed_style()
        self.img_wid.set_framed_style()

    def set_no_frame(self):
        self.data_item.is_selected = False
        self.white_text_wid.set_no_frame_style()
        self.img_wid.set_no_frame_style()

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
    rename_file = pyqtSignal(NameUrlItem)
    menu_sort_update = pyqtSignal()
    total_count_update = pyqtSignal(TotalCountItem)
    bar_path_update = pyqtSignal(str)
    move_slider = pyqtSignal(int)
    go_to_widget = pyqtSignal(str)
    paste_files = pyqtSignal()
    img_convert_win = pyqtSignal(list)

    grid_spacing = 5
    files_icon = Utils.scaled(
        qimage=QImage(os.path.join(Static.internal_images_dir, "files.png")),
        size=64
    )

    def __init__(self, main_win_item: MainWinItem):
        super().__init__()
        self.setWidgetResizable(True)
        self.horizontalScrollBar().setDisabled(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.base_signals = BaseSignals()
        self.main_win_item: MainWinItem = main_win_item
        self.url_to_wid: dict[str, Thumb] = {}
        self.cell_to_wid: dict[tuple, Thumb] = {}
        self.selected_thumbs: list[Thumb] = []
        self.wid_under_mouse: Thumb = None

        self.grid_wid = QWidget()
        self.setWidget(self.grid_wid)
        self.origin_pos = QPoint()
        self.rubberBand = QRubberBand(QRubberBand.Rectangle, self.grid_wid)

        self.grid_layout = QGridLayout()
        self.grid_wid.setLayout(self.grid_layout)
        self.grid_layout.setSpacing(self.grid_spacing)
        self.grid_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )

    def reload_rubber(self):
        self.rubberBand.deleteLater()
        self.rubberBand = QRubberBand(QRubberBand.Rectangle, self.grid_wid)
    
    def get_max_columns(self):
        try:
            return self.viewport().width() // Thumb.thumb_width
        except ZeroDivisionError:
            return 1

    def bar_path_update_cmd(self, src: str):
        QTimer.singleShot(0, lambda: self.bar_path_update.emit(src))

    def del_thumb(self, url: str):
        wid = self.url_to_wid.get(url)
        if not wid:
            return
        if wid in self.selected_thumbs:
            self.selected_thumbs.remove(wid)
        self.cell_to_wid.pop((wid.data_item.row, wid.data_item.col))
        self.url_to_wid.pop(url)
        wid.deleteLater()

    def sort(self):
        data_items = [i.data_item for i in self.url_to_wid.values()]
        sorted_data_items = DataItem.sort_(data_items, self.main_win_item.sort_item)
        new_url_to_wid = {}
        for i in sorted_data_items:
            wid = self.url_to_wid.get(i.abs_path)
            new_url_to_wid[i.abs_path] = wid
            wid.update_all(self.main_win_item.sort_item)
        self.url_to_wid = new_url_to_wid
                
    def filter(self):
        visible_thumbs = 0
        for wid in self.url_to_wid.values():
            show_widget = True
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

    def resize(self):
        Thumb.calc_size()
        for wid in self.url_to_wid.values():
            wid.update_all(self.main_win_item.sort_item)

    def rearrange(self):
        self.grid_wid.hide()
        self.cell_to_wid.clear()
        cols = self.get_max_columns()
        visible_count = 0 
        for thumb in self.url_to_wid.values():
            if thumb.data_item.must_hidden:
                continue
            row, col = divmod(visible_count, cols)
            self.add_widget_data(thumb, row, col)
            self.grid_layout.addWidget(thumb, row, col)
            visible_count += 1
        self.grid_wid.show()

    def add_widget_data(self, wid: Thumb, row: int, col: int):
        wid.data_item.row, wid.data_item.col = row, col
        self.cell_to_wid[row, col] = wid
        self.url_to_wid[wid.data_item.abs_path] = wid

    def open_thumb(self):
        if len(self.selected_thumbs) == 1:
            if self.wid_under_mouse.data_item.type_ == Static.folder_type:
                self.base_signals.history_item.emit(
                    self.wid_under_mouse.data_item.abs_path
                )
                self.base_signals.load_st_grid.emit(
                    self.wid_under_mouse.data_item.abs_path
                )
                return
            url_to_data_item = {
                url: wid.data_item
                for url, wid in self.url_to_wid.items()
                if wid.data_item.type_ != Static.folder_type
                and wid.data_item.must_hidden != True
            }
            is_selection = False
        else:
            url_to_data_item = {
                wid.data_item.abs_path: wid.data_item
                for wid in self.selected_thumbs
                if wid.data_item.type_ != Static.folder_type
                and wid.data_item.must_hidden != True
            }
            is_selection = True
        if url_to_data_item:
            item = ImgViewItem(
                current_url=self.wid_under_mouse.data_item.abs_path,
                url_to_data_item=url_to_data_item,
                is_selection=is_selection
            )
            self.base_signals.img_view.emit(item)

    def fav_cmd(self, offset: int, src: str):
        if offset == 1:
            item = NameUrlItem(
                name=os.path.basename(src),
                url=src
            )
            self.base_signals.new_fav.emit(item)
        else:
            self.base_signals.remove_fav.emit(src)

    def setup_urls_to_copy(self):
        ClipboardItemGlob.src_dir = self.main_win_item.abs_current_dir
        ClipboardItemGlob.src_urls.clear()
        for i in self.selected_thumbs:
            ClipboardItemGlob.src_urls.append(i.data_item.abs_path)

    def no_items_label_remove(self):
        wid = self.grid_wid.findChild(NoItemsLabel)
        if wid:
            wid.deleteLater()
            flags = Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
            self.grid_layout.setAlignment(flags)

    def no_items_label_create(self, text: str):
        no_images = NoItemsLabel(text)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.grid_layout.addWidget(no_images, 0, 0)
        
    def clear_selected_widgets(self):
        for i in self.selected_thumbs:
            i.set_no_frame()
        self.selected_thumbs.clear()

    def select_single_thumb(self, item: DataItem | Thumb):
        if isinstance(item, DataItem):
            thumb = self.url_to_wid[item.abs_path]
        else:
            thumb = item
        self.bar_path_update_cmd(thumb.data_item.abs_path)
        self.clear_selected_widgets()
        self.selected_thumbs.append(thumb)
        thumb.set_frame()

    def select_multiple_thumb(self, wid: Thumb):
        if isinstance(wid, Thumb):
            self.selected_thumbs.append(wid)
            wid.set_frame()

    def get_wid_under_mouse(self, a0: QMouseEvent) -> None | Thumb:
        wid = QApplication.widgetAt(a0.globalPos())
        if isinstance(wid, (WhiteTextWid, BlueTextWid, ThumbImgWidget)):
            return wid.parent()
        elif isinstance(wid, QLabel):
            return wid.parent().parent()
        else:
            return None

    def open_img_convert_win(self, urls: list[str]):
        urls = [i for i in urls if i.endswith(ImgUtils.ext_all)]
        self.img_convert_win.emit(urls)

    def set_transparent_thumbs(self):
        for i in self.selected_thumbs:
            i.set_transparent_frame(0.5)

    def setup_clipboard(self, is_cut: bool):
        if is_cut:
            self.set_transparent_thumbs()
        ClipboardItemGlob.set_is_cut(True)
        self.setup_urls_to_copy()

    def rename_file_cmd(self, filepath: str):
        item = NameUrlItem(
            name=os.path.basename(filepath),
            url=filepath
        )
        self.rename_file.emit(item)

    def folder_actions(self):
        if self.wid_under_mouse:
            root = self.wid_under_mouse.data_item.abs_path
        else:
            root = self.main_win_item.abs_current_dir

        self.context_menu.add_action(
            action=self.context_actions.new_main_win,
            callback=lambda: self.base_signals.new_main_win.emit(root)
        )
        if root in JsonData.favs:
            self.context_menu.add_action(
                action=self.context_actions.fav_remove,
                callback=lambda: self.fav_cmd(-1, root)
            )
        else:
            self.context_menu.add_action(
                action=self.context_actions.fav_add,
                callback=lambda: self.fav_cmd(1, root)
            )

    def base_thumb_actions(self):
        img_urls = []
        all_urls = []
        for i in self.selected_thumbs:
            if i.data_item.type_ != Static.folder_type:
                img_urls.append(i.data_item.abs_path)
            all_urls.append(i.data_item.abs_path)
        self.context_menu.add_action(
            action=self.context_actions.open_thumb,
            callback=lambda: self.open_thumb()
        )
        if self.wid_under_mouse.data_item.type_ == Static.folder_type:
            self.folder_actions()
        else:
            self.context_menu.add_menu(
                menu=self.context_menus.open_in_app_menu,
                callback=lambda app_path: self.base_signals.open_in_app.emit((img_urls, app_path))
            )
            self.context_menu.add_action(
                action=self.context_actions.convert_to_jpg,
                callback=lambda: self.open_img_convert_win(img_urls)
            )
        self.context_menu.addSeparator()
        self.context_menu.add_action(
            action=self.context_actions.win_info,
            callback=lambda: self.base_signals.info.emit(all_urls)
        )
        self.context_menu.add_action(
            action=self.context_actions.rename,
            callback=lambda: self.rename_file_cmd(self.wid_under_mouse.data_item.abs_path)
        )
        self.context_menu.add_action(
            action=self.context_actions.reveal,
            callback=lambda: self.base_signals.reveal_urls.emit(all_urls)
        )
        self.context_menu.addSeparator()
        self.context_menu.add_action(
            action=self.context_actions.copy_path,
            callback=lambda: self.base_signals.copy_urls.emit(all_urls)
        )
        self.context_menu.add_action(
            action=self.context_actions.copy_name,
            callback=lambda: self.base_signals.copy_names.emit(all_urls)
        )
        self.context_menu.addSeparator()
        self.context_menu.add_action(
            action=self.context_actions.cut_files,
            callback=lambda: self.setup_clipboard(is_cut=True)
        )
        self.context_menu.add_action(
            action=self.context_actions.copy_files,
            callback=lambda: self.setup_clipboard(is_cut=False)
        )
        self.context_menu.addSeparator()
        self.context_menu.add_action(
            action=self.context_actions.remove_files,
            callback=lambda: self.base_signals.remove_urls.emit(all_urls)
        )

    def base_grid_actions(self):
        urls = [self.main_win_item.abs_current_dir, ]
        self.context_menu.add_action(
            action=self.context_actions.win_info,
            callback=lambda: self.base_signals.info.emit(urls)
        )
        self.context_menu.add_action(
            action=self.context_actions.reveal,
            callback=lambda: self.base_signals.reveal_urls.emit(urls)
        )
        self.context_menu.addSeparator()
        self.context_menu.add_action(
            action=self.context_actions.copy_path,
            callback=lambda: self.base_signals.copy_urls.emit(urls)
            
        )
        self.context_menu.add_action(
            action=self.context_actions.copy_name,
            callback=lambda: self.base_signals.copy_names.emit(urls)
        )
        self.context_menu.addSeparator()
        self.context_menu.add_menu(
            menu=self.context_menus.change_view,
            callback=lambda: self.base_signals.change_view.emit()
        )
        self.context_menu.add_menu(
            menu=self.context_menus.sort_menu,
            callback=lambda: (self.sort(), self.rearrange())
        )

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
                inner_widgets = wid.findChildren((WhiteTextWid, ThumbImgWidget))
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
            self.bar_path_update_cmd(self.main_win_item.abs_current_dir)
        
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
                self.bar_path_update_cmd(self.wid_under_mouse.data_item.abs_path)
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
            self.bar_path_update_cmd(self.wid_under_mouse.data_item.abs_path)
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

            elif a0.key() == Qt.Key.Key_Up:
                self.base_signals.level_up.emit()

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
                    self.base_signals.info.emit(
                        [i.data_item.abs_path for i in self.selected_thumbs]
                    )
                else:
                    data = DataItem(self.main_win_item.abs_current_dir)
                    data.set_properties()
                    self.base_signals.info.emit([data.abs_path, ])

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
                self.base_signals.remove_urls.emit(urls)

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
                        self.get_max_columns() - 1
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
        self.wid_under_mouse = self.get_wid_under_mouse(a0)
        # клик по пустой сетке
        if not self.wid_under_mouse:
            self.clear_selected_widgets()
        # клик по виджету
        else:
            # если не было выделено ни одного виджет ранее
            # то выделяем кликнутый
            if not self.selected_thumbs:
                self.select_single_thumb(self.wid_under_mouse)
            # если есть выделенные виджеты, но кликнутый виджет не выделен
            # то снимаем выделение с других и выделяем кликнутый
            elif self.wid_under_mouse not in self.selected_thumbs:
                self.select_single_thumb(self.wid_under_mouse)
        item = TotalCountItem(
            selected=len(self.selected_thumbs),
            total=len(self.cell_to_wid)
        )
        self.total_count_update.emit(item)
        self.context_menu = UMenu()
        self.context_actions = Actions(self.context_menu)
        self.context_menus = Menus(self.context_menu, self.main_win_item)
    
    def deleteLater(self):
        urls = [i.data_item.abs_path for i in self.selected_thumbs]
        self.main_win_item.urls_to_select = urls
        return super().deleteLater()
    
    def closeEvent(self, a0):
        urls = [i.src for i in self.selected_thumbs]
        self.main_win_item.urls_to_select = urls
        return super().closeEvent(a0)
