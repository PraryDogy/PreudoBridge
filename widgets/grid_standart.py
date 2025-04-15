import gc
import os

from PyQt5.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QPixmap
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import QLabel

from cfg import Dynamic, Static
from database import Dbase, OrderItem
from utils import URunnable, UThreadPool, Utils

from .finder_items import FinderItems, LoadingWid
from .grid import Grid, Thumb, ThumbFolder
from .grid_tools import GridTools
from .win_copy_files import WinCopyFiles, ErrorWin

WARN_TEXT = "Папка пуста или нет подключения к диску"
TASK_NAME = "LOAD_IMAGES"
JPG_PNG_EXTS: tuple = (".jpg", ".jpeg", ".jfif", "png")
TIFF_EXTS: tuple = (".tif", ".tiff")
PSD_EXTS: tuple = (".psd", ".psb")


class WorkerSignals(QObject):
    new_widget = pyqtSignal(OrderItem)
    finished_ = pyqtSignal()


class LoadImages(URunnable):
    def __init__(self, main_dir: str, order_items: list[OrderItem]):
        super().__init__()
        self.signals_ = WorkerSignals()
        self.main_dir = main_dir
        self.order_items = order_items
        # key_ = lambda x: (self.order_priority(item=x), x.size)
        key_ = lambda x: x.size
        self.order_items.sort(key=key_)

    @URunnable.set_running_state
    def run(self):

        # чтобы не создавать пустую ДБ в пустых или папочных директориях

        if not self.order_items:
            return

        db = os.path.join(self.main_dir, Static.DB_FILENAME)
        self.dbase = Dbase()
        engine = self.dbase.create_engine(path=db)

        if engine is None:
            return

        self.conn = engine.connect()
        self.process_order_items()
        self.conn.close()

        try:
            self.signals_.finished_.emit()
        except RuntimeError:
            ...

    def order_priority(self, item:OrderItem):
        if item.type_ in JPG_PNG_EXTS:
            return 0
        elif item.type_ in TIFF_EXTS:
            return 1
        elif item.type_ in PSD_EXTS:
            return 2
        return 3

    def process_order_items(self):

        for order_item in self.order_items:

            if not self.should_run:
                return
                        
            try:

                new_order_item = GridTools.update_order_item(
                    conn=self.conn,
                    order_item=order_item
                )

                if new_order_item:
                    self.signals_.new_widget.emit(new_order_item)

            except RuntimeError:
                return

            except Exception as e:
                Utils.print_error(parent=self, error=e)
                continue


class GridStandart(Grid):
    def __init__(self, main_dir: str, view_index: int, path_for_select: str):
        super().__init__(main_dir, view_index, path_for_select)

        self.loaded_images: list[str] = []

        self.load_images_timer = QTimer(self)
        self.load_images_timer.setSingleShot(True)
        self.load_images_timer.timeout.connect(self.load_visible_images)
        self.load_images_threads: list[LoadImages] = []
        self.verticalScrollBar().valueChanged.connect(self.on_scroll_changed)
        self.tasks: list[LoadImages] = []

        self.loading_lbl = LoadingWid(parent=self)
        self.loading_lbl.center(self)
        self.show()

        self.finder_thread = FinderItems(self.main_dir)
        self.finder_thread.signals_.finished_.connect(self.finder_thread_fin)
        UThreadPool.start(self.finder_thread)

    def load_visible_images(self):
        visible_widgets: list[Thumb] = []
        
        for widget in self.main_wid.findChildren(Thumb):
            if not widget.visibleRegion().isEmpty():
                visible_widgets.append(widget)

        ordered_items = [
            OrderItem(
                src=i.src,
                size=i.size,
                mod=i.mod,
                rating=i.rating
            )
            for i in visible_widgets
            if i.src not in self.loaded_images
        ]

        self.run_load_images_thread(cut_order_items=ordered_items)

    def on_scroll_changed(self, value: int):
        self.load_images_timer.stop()
        self.load_images_timer.start(1000)

    def finder_thread_fin(self, items: tuple[list[OrderItem]]):
        order_items, new_items = items

        del self.finder_thread
        gc.collect()

        self.loading_lbl.hide()
        total = len(order_items)

        self.bar_bottom_update.emit((self.main_dir, total))
        sys_disk = Utils.get_system_volume()
        Thumb.calculate_size()
        col_count = self.get_col_count()

        if not order_items:
            no_images = QLabel(text=WARN_TEXT)
            no_images.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.addWidget(no_images, 0, 0)
            return

        row, col = 0, 0

        exts = {i.type_ for i in order_items}
        for ext in exts:
            icon_path = Utils.get_generic_icon_path(ext)
            if icon_path not in Dynamic.GENERIC_ICON_PATHS:
                path_to_svg = Utils.create_generic_icon(ext)
                Dynamic.GENERIC_ICON_PATHS.append(path_to_svg)

        for order_item in order_items:

            wid = Thumb(
                src=order_item.src,
                size=order_item.size,
                mod=order_item.mod,
                rating=order_item.rating,
                )
            
            if wid.type_ == Static.FOLDER_TYPE:
                wid.set_svg_icon(Static.FOLDER_SVG)
            
            else:
                icon = Utils.get_generic_icon_path(order_item.type_)
                icon = Dynamic.GENERIC_ICON_PATHS.get(icon)
                wid.set_svg_icon(icon)
            
            if order_item in new_items:
                wid.set_green_text()

            self.add_widget_data(wid=wid, row=row, col=col)
            self.grid_layout.addWidget(wid, row, col)

            col += 1
            if col >= col_count:
                col = 0
                row += 1

        self.order_()
        self.rearrange()

        if Dynamic.rating_filter > 0:
            self.filter_()
            self.rearrange()

        self.load_images_timer.start(100)
        
    def run_load_images_thread(self, cut_order_items: list[OrderItem]):

        for i in self.load_images_threads:
            i.should_run = False

        thread_ = LoadImages(self.main_dir, cut_order_items)
        self.load_images_threads.append(thread_)
        thread_.signals_.new_widget.connect(
            lambda image_data: self.set_pixmap(image_data)
        )
        thread_.signals_.finished_.connect(
            lambda: self.finalize_load_images_thread(thread_=thread_)
        )
        UThreadPool.start(thread_)
    
    def finalize_load_images_thread(self, thread_: LoadImages):
        self.load_images_threads.remove(thread_)
        del thread_
        gc.collect()

    def set_pixmap(self, order_item: OrderItem):
        try:

            widget = self.path_to_wid.get(order_item.src)

            if isinstance(widget, Thumb):

                if isinstance(order_item.pixmap_, QPixmap):
                    widget.set_pixmap(pixmap=order_item.pixmap_)

                if isinstance(order_item.rating, int):
                    widget.set_db_rating(rating=order_item.rating)

                self.loaded_images.append(order_item.src)

        except RuntimeError:
            ...

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        
        for i in self.load_images_threads:
            i.should_run = False

        return super().closeEvent(a0)

    def resizeEvent(self, a0):
        self.loading_lbl.center(self)
        return super().resizeEvent(a0)
    
    def dragEnterEvent(self, a0):
        if a0.mimeData().hasUrls():
            a0.acceptProposedAction()
        return super().dragEnterEvent(a0)
    
    def dropEvent(self, a0):
        Dynamic.files_to_copy = [i.toLocalFile() for i in a0.mimeData().urls()]

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
            self.win_copy_files_win = WinCopyFiles(self.main_dir)
            self.win_copy_files_win.load_st_grid_sig.connect(self.load_st_grid_sig.emit)
            self.win_copy_files_win.error_win_sig.connect(self.error_win_cmd)
            self.win_copy_files_win.center(self.window())
            self.win_copy_files_win.show()

        return super().dropEvent(a0)
    
    def error_win_cmd(self):
        self.win_copy_files_win.close()
        self.error_win = ErrorWin()
        self.error_win.center(self.window())
        self.error_win.show()
