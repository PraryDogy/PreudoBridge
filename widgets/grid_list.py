import gc
import os
import sys

from PyQt5.QtCore import (QDateTime, QDir, QItemSelectionModel, QMimeData,
                          QModelIndex, Qt, QTimer, QUrl, pyqtSignal)
from PyQt5.QtGui import (QContextMenuEvent, QDrag, QDragEnterEvent,
                         QDragMoveEvent, QDropEvent, QKeyEvent, QPixmap)
from PyQt5.QtWidgets import (QAbstractItemView, QApplication, QFileSystemModel,
                             QSplitter, QTableView, QTreeView)

from cfg import Dynamic, JsonData, Static
from evlosh_templates.evlosh_utils import EvloshUtils
from system.items import CopyItem, MainWinItem
from system.utils import Utils

from ._base_widgets import LoadingWid, UMenu
from .actions import GridActions, ItemActions
from .archive_win import ArchiveWin
from .copy_files_win import CopyFilesWin, ErrorWin
from .grid import Thumb
from .img_convert_win import ImgConvertWin
from .info_win import InfoWin
from .remove_files_win import RemoveFilesWin
from .rename_win import RenameWin


class MyFileSystemModel(QFileSystemModel):
    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            headers = ["Имя", "Размер", "Тип", "Дата изменения"]
            if 0 <= section < len(headers):
                return headers[section]
        return super().headerData(section, orientation, role)

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            col = index.column()
            if col == 1:  # Размер
                size = self.size(index)
                if size == 0 and self.isDir(index):
                    return ""
                elif size < 1024:
                    return f"{size} байт"
                elif size < 1024**2:
                    return f"{size/1024:.1f} КБ"
                elif size < 1024**3:
                    return f"{size/1024**2:.1f} МБ"
                else:
                    return f"{size/1024**3:.1f} ГБ"
            elif col == 2:  # Тип
                path = self.filePath(index)
                if self.isDir(index):
                    return "Папка"
                else:
                    ext = os.path.splitext(path)[1].lower()
                    if ext:
                        return f"Файл {ext[1:].upper()}"
                    return "Файл"
            elif col == 3:  # Дата
                dt = self.lastModified(index)
                if isinstance(dt, QDateTime):
                    return dt.toString("dd.MM.yyyy HH:mm")
        return super().data(index, role)


class GridList(QTableView):
    col: int = 0
    order: int = 0
    sizes: list = [250, 100, 100, 150]

    new_history_item = pyqtSignal(str)
    path_bar_update = pyqtSignal(str)
    add_fav = pyqtSignal(str)
    del_fav = pyqtSignal(str)
    load_st_grid = pyqtSignal()
    move_slider = pyqtSignal(int)
    change_view = pyqtSignal()
    open_in_new_win = pyqtSignal(str)
    level_up = pyqtSignal()
    sort_menu_update = pyqtSignal()
    total_count_update = pyqtSignal(tuple)
    finished_ = pyqtSignal()

    def __init__(self, main_win_item: MainWinItem):
        super().__init__()

        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDropIndicatorShown(True)

        self.main_win_item = main_win_item
        self.url_to_index: dict[str, QModelIndex] = {}
        self.main_win_item = main_win_item

        self.loading_lbl = LoadingWid(parent=self)
        self.loading_lbl.center(self)
        self.show()

        self.setSelectionBehavior(QTableView.SelectRows)
        self.setSortingEnabled(True)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().sectionClicked.connect(self.save_sort_settings)
        self.doubleClicked.connect(self.double_clicked)

        self._model = MyFileSystemModel()
        self._model.setRootPath(self.main_win_item.main_dir)

        self._model.setFilter(QDir.AllEntries | QDir.NoDotAndDotDot)
        if JsonData.show_hidden:
            self._model.setFilter(self._model.filter() | QDir.Hidden)

        self.setModel(self._model)
        self.setRootIndex(self._model.index(self.main_win_item.main_dir))

        self.sortByColumn(GridList.col, GridList.order)
        for i in range(0, 4):
            self.setColumnWidth(i, GridList.sizes[i])

        self._model.directoryLoaded.connect(self.set_url_to_index_)

    def set_url_to_index_(self):
        self.hide()

        root_index = self.rootIndex()
        row_count = self._model.rowCount(root_index)
    
        for row in range(row_count):
            index = self._model.index(row, 0, root_index)
            path = self._model.filePath(index)
            self.url_to_index[path] = index

        if self.main_win_item.get_go_to():
            if self.main_win_item.get_go_to() in self.url_to_index:
                index = self.url_to_index.get(self.main_win_item.get_go_to())
                if index and index.isValid():
                    self.select_row(index)
                self.main_win_item.clear_go_to()

        elif self.main_win_item.get_urls_to_select():
            for url in self.main_win_item.get_urls_to_select():
                if url in self.url_to_index:
                    index = self.url_to_index.get(url)
                    self.select_row(index)
            self.main_win_item.clear_urls_to_select()
            QTimer.singleShot(100, lambda: self.verticalScrollBar().setValue(0))

        self.setCurrentIndex(QModelIndex())
        self.path_bar_update.emit(self.main_win_item.main_dir)
        self.total_count_update.emit((0, row_count))
        self.loading_lbl.hide()

        self.show()

        self.finished_.emit()

    def select_path(self, path: str):
        index = self._model.index(path, 0)
        self.select_row(index)

    def set_first_col_width(self):
        left_menu_w = self.window().findChild(QSplitter).sizes()[0]
        win_w = self.window().width()
        columns_w = sum(GridList.sizes[1:])
        new_w = win_w - left_menu_w - columns_w - 30
        self.setColumnWidth(0, new_w)

    def double_clicked(self, index):
        self.open_thumb(self.get_selected_urls())

    def open_thumb(self, urls: list[str]):
        if len(urls) == 1:
            if urls[0].endswith(Static.ext_all):
                url_to_wid = {
                    url: Thumb(url)
                    for url, v in self.url_to_index.items()
                    if url.endswith(Static.ext_all)
                }
                start_url = urls[0]
                is_selection = False
                self.open_img_view(start_url, url_to_wid, is_selection)
            elif os.path.isdir(urls[0]):
                self.main_win_item.main_dir = urls[0]
                self.new_history_item.emit(urls[0])
                self.load_st_grid.emit()
            else:
                Utils.open_in_def_app(urls[0])
        else:
            url_to_wid = {
                url: Thumb(url)
                for url in urls
                if url.endswith(Static.ext_all)
            }
            if url_to_wid:
                start_url = list(url_to_wid)[0]
                is_selection = True
                self.open_img_view(start_url, url_to_wid, is_selection)

            folders = [
                i
                for i in urls
                if os.path.isdir(i)
            ]

            for i in folders:
                self.open_in_new_win.emit(i)

            files = [
                i
                for i in urls
                if not i.endswith(Static.ext_all)
                and
                os.path.isfile(i)
            ]

            for i in files:
                Utils.open_in_def_app(i)

    def open_img_view(self, start_url: str, url_to_wid: dict, is_selection: bool):
        from .img_view_win import ImgViewWin
        self.img_view_win = ImgViewWin(start_url, url_to_wid, is_selection)
        self.img_view_win.move_to_url.connect(lambda path: self.select_path(path))
        self.img_view_win.closed.connect(self.img_view_closed)
        self.img_view_win.center(self.window())
        self.img_view_win.show()

    def img_view_closed(self):
        del self.img_view_win
        gc.collect()

    def save_sort_settings(self, index):
        GridList.col = index
        GridList.order = self.horizontalHeader().sortIndicatorOrder()
        self.sortByColumn(GridList.col, GridList.order)

    def toggle_is_cut(self, value: bool):
        Dynamic.is_cut = value

    def rearrange_thumbs(self, *args, **kwargs):
        ...

    def sort_thumbs(self, *args, **kwargs):
        ...

    def filter_thumbs(self, *args, **kwargs):
        ...

    def resize_thumbs(self, *args, **kwargs):
        ...

    def win_info_cmd(self, src: str):
        """
        Открыть окно информации о файле / папке
        """
        self.win_info = InfoWin(src)
        self.win_info.finished_.connect(lambda: self.win_info_fin())

    def win_info_fin(self):
        self.win_info.center(self.window())
        self.win_info.show()

    def get_selected_urls(self):
        urls = []
        selection_model = self.selectionModel()
        selected_rows = selection_model.selectedRows()
        for index in selected_rows:
            file_path = self._model.filePath(index)  # Получаем путь по индексу
            urls.append(file_path)
        return urls

    def open_img_convert_win(self, urls: list[str]):

        def finished_(urls: list[str]):
            QTimer.singleShot(300, lambda: self.select_path(urls[-1]))
            self.convert_win.deleteLater()

        urls = [i for i in urls if i.endswith(Static.ext_all)]
        self.convert_win = ImgConvertWin(urls)
        self.convert_win.center(self.window())
        self.convert_win.finished_.connect(lambda urls: finished_(urls))
        self.convert_win.show()

    def make_archive(self, urls: list[str]):

        def finished(*args):
            QTimer.singleShot(300, lambda: self.select_path(zip_path))

        zip_path = os.path.join(self.main_win_item.main_dir, "архив.zip")
        self.archive_win = ArchiveWin(urls, zip_path)
        self.archive_win.finished_.connect(finished)
        self.archive_win.center(self.window())
        self.archive_win.show()

    def rename_row(self, url: str):
        
        def finished(text: str, ext: str):
            filename = text + ext
            root = os.path.dirname(url)
            new_url = os.path.join(root, filename)
            os.rename(url, new_url)
            QTimer.singleShot(500, lambda: self.select_path(new_url))

        name, ext = os.path.splitext(url)
        name = os.path.basename(name)

        self.rename_row = RenameWin(name)
        self.rename_row.finished_.connect(lambda text: finished(text, ext))
        self.rename_row.center(self.window())
        self.rename_row.show()

    def item_context(self, menu_: UMenu, selected_path: str, urls: list[str], names: list[str], total: int):
        urls = self.get_selected_urls()

        view_action = ItemActions.OpenThumb(menu_)
        view_action.triggered.connect(lambda: self.open_thumb(urls))
        menu_.addAction(view_action)

        open_in_app = ItemActions.OpenInApp(menu_, urls)
        menu_.addMenu(open_in_app)

        info = ItemActions.Info(menu_)
        info.triggered.connect(lambda: self.win_info_cmd(selected_path))
        menu_.addAction(info)


        if selected_path.endswith(Static.ext_all):
            convert_action = ItemActions.ImgConvert(menu_)
            convert_action.triggered.connect(lambda: self.open_img_convert_win(urls))
            menu_.addAction(convert_action)

        archive = ItemActions.MakeArchive(menu_)
        archive.triggered.connect(lambda: self.make_archive(urls))
        menu_.addAction(archive)

        if os.path.isdir(selected_path):
            if selected_path in JsonData.favs:
                cmd_ = lambda: self.del_fav.emit(selected_path)
                fav_action = ItemActions.FavRemove(menu_)
                fav_action.triggered.connect(cmd_)
                menu_.addAction(fav_action)
            else:
                cmd_ = lambda: self.add_fav.emit(selected_path)
                fav_action = ItemActions.FavAdd(menu_)
                fav_action.triggered.connect(cmd_)
                menu_.addAction(fav_action)

        menu_.addSeparator()

        open_finder_action = ItemActions.RevealInFinder(menu_, urls)
        menu_.addAction(open_finder_action)

        copy_path_action = ItemActions.CopyPath(menu_, urls)
        copy_path_action.triggered.connect(CopyItem.reset)
        menu_.addAction(copy_path_action)

        copy_name = ItemActions.CopyName(menu_, names)
        copy_path_action.triggered.connect(CopyItem.reset)
        menu_.addAction(copy_name)

        menu_.addSeparator()

        if CopyItem.urls:
            paste_files = GridActions.PasteObjects(menu_)
            paste_files.triggered.connect(self.paste_files)
            menu_.addAction(paste_files)

            menu_.addSeparator()

        rename = ItemActions.Rename(menu_)
        rename.triggered.connect(lambda: self.rename_row(selected_path))
        menu_.addAction(rename)

        cut_objects = ItemActions.CutObjects(menu_)
        cut_objects.triggered.connect(lambda e: CopyItem.set_is_cut(True))
        cut_objects.triggered.connect(lambda e: self.setup_urls_to_copy(urls))
        menu_.addAction(cut_objects)

        copy_files = ItemActions.CopyObjects(menu_)
        copy_files.triggered.connect(lambda e: CopyItem.set_is_cut(False))
        copy_files.triggered.connect(lambda e: self.setup_urls_to_copy(urls))
        menu_.addAction(copy_files)

        remove_objects = ItemActions.RemoveObjects(menu_)
        remove_objects.triggered.connect(lambda: self.remove_files_cmd(urls))
        menu_.addAction(remove_objects)  

    def grid_context(self, menu_: UMenu, selected_path: str, urls: list[str], names: list[str], total: int):
        info = GridActions.Info(menu_)
        info.triggered.connect(lambda: self.win_info_cmd(selected_path))
        menu_.addAction(info)

        if os.path.isdir(selected_path):
            if selected_path in JsonData.favs:
                cmd_ = lambda: self.del_fav.emit(selected_path)
                fav_action = GridActions.FavRemove(menu_)
                fav_action.triggered.connect(cmd_)
                menu_.addAction(fav_action)
            else:
                cmd_ = lambda: self.add_fav.emit(selected_path)
                fav_action = GridActions.FavAdd(menu_)
                fav_action.triggered.connect(cmd_)
                menu_.addAction(fav_action)

        menu_.addSeparator()

        open_finder_action = GridActions.RevealInFinder(menu_, urls)
        menu_.addAction(open_finder_action)

        copy_path_action = GridActions.CopyPath(menu_, urls)
        copy_path_action.triggered.connect(CopyItem.reset)
        menu_.addAction(copy_path_action)

        copy_name = GridActions.CopyName(menu_, names)
        copy_name.triggered.connect(CopyItem.reset)
        menu_.addAction(copy_name)

        menu_.addSeparator()

        if CopyItem.urls:
            paste_files = GridActions.PasteObjects(menu_)
            paste_files.triggered.connect(self.paste_files)
            menu_.addAction(paste_files)
            menu_.addSeparator()

        upd_ = GridActions.UpdateGrid(menu_)
        upd_.triggered.connect(lambda: self.load_st_grid.emit())
        menu_.addAction(upd_)

        change_view = GridActions.ChangeViewMenu(menu_, self.main_win_item.get_view_mode())
        change_view.triggered.connect(lambda: self.change_view.emit())
        menu_.addMenu(change_view)

    def paste_files(self):

        def finalize(urls: list[str]):
            self.main_win_item.set_urls_to_select(urls)
            if CopyItem.get_is_cut():
                CopyItem.reset()
            self.load_st_grid.emit()

        CopyItem.set_dest(self.main_win_item.main_dir)
        self.win_copy = CopyFilesWin()
        self.win_copy.finished_.connect(finalize)
        self.win_copy.error_win.connect(self.show_error_win)
        self.win_copy.center(self.window())
        self.win_copy.show()
        QTimer.singleShot(300, self.win_copy.raise_)

    def show_error_win(self):
        """
        Открывает окно ошибки копирования файлов
        """
        self.win_copy.deleteLater()
        self.error_win = ErrorWin()
        self.error_win.center(self.window())
        self.error_win.show()

    def setup_urls_to_copy(self, urls: list[str]):
        CopyItem.set_src(self.main_win_item.main_dir)
        CopyItem.set_is_search(False)
        CopyItem.urls.clear()
        for i in urls:
            CopyItem.urls.append(i)

    def remove_files_cmd(self, urls: list[str]):
        self.rem_win = RemoveFilesWin(self.main_win_item, urls)
        self.rem_win.finished_.connect(lambda urls: self.load_st_grid.emit())
        self.rem_win.center(self.window())
        self.rem_win.show()

    def select_row(self, index: QModelIndex):
        try:
            self.setCurrentIndex(index)
            tags = QItemSelectionModel.Select | QItemSelectionModel.Rows
            self.selectionModel().select(index, tags)
        except RuntimeError:
            print("OK, grid_list > select_row > grid was deleted")

    def contextMenuEvent(self, event: QContextMenuEvent):
        # определяем выделена ли строка
        index = self.indexAt(event.pos())
        selected_path = self._model.filePath(index)
        menu_ = UMenu(parent=self)

        if index.isValid():
            urls = self.get_selected_urls()
            if selected_path not in urls:
                self.select_row(index)
            urls = self.get_selected_urls()
            names = [os.path.basename(i) for i in urls]
            total = len(urls)
            self.item_context(menu_, selected_path, urls, names, total)
        else:
            selected_path = self.main_win_item.main_dir
            urls = [self.main_win_item.main_dir]
            names = [os.path.basename(i) for i in urls]
            total = len(urls)
            self.grid_context(menu_, selected_path, urls, names, total)

        menu_.show_under_cursor()

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.modifiers() & Qt.KeyboardModifier.ControlModifier:

            if a0.key() == Qt.Key.Key_Up:
                self.level_up.emit()

            elif a0.key() == Qt.Key.Key_Down:
                index = self.currentIndex()
                self.double_clicked(index)
                # return
            
            elif a0.key() == Qt.Key.Key_I:
                index = self.currentIndex()
                path = self._model.filePath(index)
                self.win_info_cmd(path)
                # return

            elif a0.key() == Qt.Key.Key_Backspace:
                urls = self.get_selected_urls()
                if urls:
                    self.remove_files_cmd(urls)

            elif a0.key() == Qt.Key.Key_X:
                urls = self.get_selected_urls()
                if urls:
                    CopyItem.set_is_cut(True)
                    self.setup_urls_to_copy(urls)

            elif a0.key() == Qt.Key.Key_C:
                urls = self.get_selected_urls()
                if urls:
                    CopyItem.set_is_cut(False)
                    self.setup_urls_to_copy(urls)

            elif a0.key() == Qt.Key.Key_V:
                if CopyItem.urls:
                    self.paste_files()

        elif a0.key() in (Qt.Key.Key_Return, Qt.Key.Key_Space):
            index = self.currentIndex()
            self.double_clicked(index)
            # return

        return super().keyPressEvent(a0)

    def dragEnterEvent(self, a0: QDragEnterEvent):
        if a0.mimeData().hasUrls():
            a0.acceptProposedAction()
    
    def dragMoveEvent(self, event: QDragMoveEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, a0: QDropEvent):
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
        if src == self.main_win_item.main_dir:
            print("нельзя копировать в себя через DropEvent")
            return
        else:
            CopyItem.set_src(src)
            CopyItem.urls = urls
            self.paste_files()
        return super().dropEvent(a0)
    
    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        self.drag_start_position = e.pos()
        return super().mousePressEvent(e)
    
    def mouseMoveEvent(self, e):
        try:
            distance = (e.pos() - self.drag_start_position).manhattanLength()
        except AttributeError:
            return

        if distance < QApplication.startDragDistance():
            return
        
        urls = self.get_selected_urls()
        

        self.drag = QDrag(self)
        self.mime_data = QMimeData()

        img_ = QPixmap(Static.COPY_FILES_SVG)
        self.drag.setPixmap(img_)
        
        urls = [
            QUrl.fromLocalFile(i)
            for i in urls
            ]

        if urls:
            self.mime_data.setUrls(urls)

            self.drag.setMimeData(self.mime_data)
            self.drag.exec_(Qt.DropAction.CopyAction)
        return super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        index = self.indexAt(e.pos())
        if not index.isValid():
            self.clearSelection()
            self.setCurrentIndex(QModelIndex())
        super().mouseReleaseEvent(e)

    def deleteLater(self):
        urls = self.get_selected_urls()
        self.main_win_item.set_urls_to_select(urls)
        return super().deleteLater()
    
    def close(self):
        urls = self.get_selected_urls()
        self.main_win_item.set_urls_to_select(urls)
        return super().close()
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.model():
            total_width = self.viewport().width()
            other_width = sum(self.columnWidth(i) for i in range(1, self.model().columnCount()))
            self.setColumnWidth(0, total_width - other_width)