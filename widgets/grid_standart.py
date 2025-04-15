import gc
import os

from PyQt5.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QPixmap
from PyQt5.QtWidgets import QLabel

from cfg import Dynamic, Static
from database import Dbase
from utils import URunnable, UThreadPool, Utils

from ._base_widgets import BaseItem
from .finder_items import FinderItems, LoadingWid
from .grid import Grid, Thumb
from .grid_tools import GridTools
from .win_copy_files import ErrorWin, WinCopyFiles

WARN_TEXT = "Папка пуста или нет подключения к диску"
TASK_NAME = "LOAD_IMAGES"
JPG_PNG_EXTS: tuple = (".jpg", ".jpeg", ".jfif", "png")
TIFF_EXTS: tuple = (".tif", ".tiff")
PSD_EXTS: tuple = (".psd", ".psb")


class WorkerSignals(QObject):
    update_thumb = pyqtSignal(Thumb)
    finished_ = pyqtSignal()


class LoadImages(URunnable):
    def __init__(self, main_dir: str, thumbs: list[Thumb]):
        super().__init__()
        self.signals_ = WorkerSignals()
        self.main_dir = main_dir
        self.thumbs = thumbs
        # key_ = lambda x: (self.order_priority(item=x), x.size)
        key_ = lambda x: x.size
        self.thumbs.sort(key=key_)

    @URunnable.set_running_state
    def run(self):

        # чтобы не создавать пустую ДБ в пустых или папочных директориях

        if not self.thumbs:
            return

        db = os.path.join(self.main_dir, Static.DB_FILENAME)
        self.dbase = Dbase()
        engine = self.dbase.create_engine(path=db)

        if engine is None:
            return

        self.conn = engine.connect()
        self.process_thumbs()
        self.conn.close()

        try:
            self.signals_.finished_.emit()
        except RuntimeError:
            ...

    def order_priority(self, item: Thumb):
        if item.type_ in JPG_PNG_EXTS:
            return 0
        elif item.type_ in TIFF_EXTS:
            return 1
        elif item.type_ in PSD_EXTS:
            return 2
        return 3

    def process_thumbs(self):
        for thumb in self.thumbs:

            if not self.should_run:
                return
                        
            try:
                updated_thumb = GridTools.update_thumb(self.conn, thumb)
                if updated_thumb:
                    self.signals_.update_thumb.emit(updated_thumb)
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

        thumbs = [
            i
            for i in visible_widgets
            if i.src not in self.loaded_images
        ]

        self.run_load_images_thread(thumbs)

    def on_scroll_changed(self, value: int):
        self.load_images_timer.stop()
        self.load_images_timer.start(1000)

    def finder_thread_fin(self, items: tuple[list[BaseItem]]):
        base_items, new_items = items

        del self.finder_thread
        gc.collect()

        self.loading_lbl.hide()
        total = len(base_items)

        self.bar_bottom_update.emit((self.main_dir, total))
        Thumb.calculate_size()
        col_count = self.get_col_count()

        if not base_items:
            no_images = QLabel(text=WARN_TEXT)
            no_images.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.addWidget(no_images, 0, 0)
            return

        row, col = 0, 0


        # создаем генерик иконки если не было
        exts = {i.type_ for i in base_items}
        for ext in exts:
            icon_path = Utils.get_generic_icon_path(ext)
            if icon_path not in Dynamic.GENERIC_ICON_PATHS:
                path_to_svg = Utils.create_generic_icon(ext)
                Dynamic.GENERIC_ICON_PATHS.append(path_to_svg)

        for base_item in base_items:

            thumb = Thumb(base_item.src, base_item.size, base_item.mod, base_item.rating)
            thumb.set_src()
            thumb.set_name()
            thumb.set_file_type()
            thumb.setup_child_widgets()
            thumb.set_no_frame()

            if base_item.src.count(os.sep) == 2:
                thumb.set_svg_icon(Static.HDD_SVG)

            elif base_item.type_ == Static.FOLDER_TYPE:
                thumb.set_svg_icon(Static.FOLDER_SVG)

            else:
                icon_path = Utils.get_generic_icon_path(base_item.type_)
                thumb.set_svg_icon(icon_path)
            
            if base_item in new_items:
                thumb.set_green_text()

            self.add_widget_data(wid=thumb, row=row, col=col)
            self.grid_layout.addWidget(thumb, row, col)

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
        
    def run_load_images_thread(self, thumbs: list[Thumb]):

        for i in self.load_images_threads:
            i.should_run = False

        thread_ = LoadImages(self.main_dir, thumbs)
        self.load_images_threads.append(thread_)
        thread_.signals_.update_thumb.connect(
            lambda image_data: self.set_image(image_data)
        )
        thread_.signals_.finished_.connect(
            lambda: self.finalize_load_images_thread(thread_=thread_)
        )
        UThreadPool.start(thread_)
    
    def finalize_load_images_thread(self, thread_: LoadImages):
        self.load_images_threads.remove(thread_)
        del thread_
        gc.collect()

    def set_image(self, base_item: Thumb):
        try:
            widget = self.path_to_wid.get(base_item.src)
            if widget:
                if base_item.get_pixmap_storage():
                    widget.set_image(base_item.get_pixmap_storage())
                if isinstance(base_item.rating, int):
                    widget.set_db_rating(rating=base_item.rating)
                self.loaded_images.append(base_item.src)

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
