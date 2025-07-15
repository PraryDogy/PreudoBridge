import gc
import os
import subprocess

from PyQt5.QtCore import (QDir, QItemSelectionModel, QMimeData, QModelIndex,
                          Qt, QTimer, QUrl)
from PyQt5.QtGui import (QContextMenuEvent, QDrag, QDragEnterEvent,
                         QDragMoveEvent, QDropEvent, QKeyEvent, QPixmap)
from PyQt5.QtWidgets import (QAbstractItemView, QApplication, QFileSystemModel,
                             QSplitter, QTableView)

from cfg import Dynamic, JsonData, Static
from utils import Utils

from ._base_items import MainWinItem, UMenu, UTableView
from .actions import GridActions, ItemActions
from .copy_files_win import CopyFilesWin, ErrorWin
from .finder_items import LoadingWid
from .grid import Thumb
from .info_win import InfoWin
from .remove_files_win import RemoveFilesWin


class GridList(UTableView):
    col: int = 0
    order: int = 0
    sizes: list = [250, 100, 100, 150]

    def __init__(self, main_win_item: MainWinItem, view_index: int):
        super().__init__()

        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDropIndicatorShown(True)

        self.main_win_item = main_win_item
        self.view_index = view_index
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

        self._model = QFileSystemModel()
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

        elif self.main_win_item.get_urls():
            for url in self.main_win_item.get_urls():
                if url in self.url_to_index:
                    index = self.url_to_index.get(url)
                    self.select_row(index)
            self.main_win_item.clear_urls()
            QTimer.singleShot(100, lambda: self.verticalScrollBar().setValue(0))

        self.setCurrentIndex(QModelIndex())
        self.path_bar_update.emit(self.main_win_item.main_dir)
        self.total_count_update.emit(row_count)
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
        self.get_selected_urls()
        self.open_thumb()

    def open_thumb(self, urls: list[str]):
        if len(urls) == 1:

            if urls[0].endswith(Static.ext_all):
                url_to_wid = {
                    url: wid
                    for url, wid in self.url_to_wid.items()
                    if url.endswith(Static.ext_all)
                }
                is_selection = False
                self.open_img_view(wid.src, url_to_wid, is_selection)
            elif os.path.isdir(urls[0]):
                self.main_win_item.main_dir = urls[0]
                self.new_history_item.emit(urls[0])
                self.load_st_grid.emit()
            else:
                Utils.open_in_def_app(urls[0])
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
                Utils.open_in_def_app(i)

    def open_img_view(self):
        from .img_view_win import ImgViewWin

        url_to_wid = {
            url: Thumb(url)
            for url, index in self.url_to_index.items()
            if url.endswith(Static.ext_all)
        }

        cmd = lambda path: self.select_path(path)
        self.img_view_win = ImgViewWin(path, url_to_wid, False)
        self.img_view_win.move_to_url.connect(cmd)
        self.img_view_win.closed.connect(self.img_view_closed)
        self.img_view_win.center(self.window())
        self.img_view_win.show()

    # def view_cmd(self, path: str):
    #     if os.path.isdir(path):
    #         self.main_win_item.main_dir = path
    #         self.load_st_grid.emit()
    #         self.new_history_item.emit(path)

    #     elif path.endswith(Static.ext_all):
    #         from .img_view_win import ImgViewWin

    #         url_to_wid = {
    #             url: Thumb(url)
    #             for url, index in self.url_to_index.items()
    #             if url.endswith(Static.ext_all)
    #         }

    #         cmd = lambda path: self.select_path(path)
    #         self.img_view_win = ImgViewWin(path, url_to_wid, False)
    #         self.img_view_win.move_to_url.connect(cmd)
    #         self.img_view_win.closed.connect(self.img_view_closed)
    #         self.img_view_win.center(self.window())
    #         self.img_view_win.show()

    #     else:
    #         subprocess.Popen(["open", path])

    def img_view_closed(self):
        gc.collect()

    def save_sort_settings(self, index):
        GridList.col = index
        GridList.order = self.horizontalHeader().sortIndicatorOrder()
        self.sortByColumn(GridList.col, GridList.order)

    def rearrange_thumbs(self, *args, **kwargs):
        ...

    def sort_thumbs(self, *args, **kwargs):
        ...

    def filter_thumbs(self, *args, **kwargs):
        ...

    def resize_thumbs(self, *args, **kwargs):
        ...

    def win_info_cmd(self, src: str):
        self.win_info = InfoWin(src)
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

    def item_context(self, menu_: UMenu, selected_path: str, urls: list[str], names: list[str], total: int):
        urls = self.get_selected_urls()

        view_action = ItemActions.OpenThumb(menu_, urls)
        view_action.triggered.connect(lambda: self.open_thumb(urls))
        menu_.addAction(view_action)

        open_in_app = ItemActions.OpenInApp(menu_, urls)
        menu_.addMenu(open_in_app)

        menu_.addSeparator()

        info = ItemActions.Info(menu_)
        info.triggered.connect(lambda: self.win_info_cmd(selected_path))
        menu_.addAction(info)

        open_finder_action = ItemActions.RevealInFinder(menu_, urls, total)
        menu_.addAction(open_finder_action)

        copy_path_action = ItemActions.CopyPath(menu_, urls, total)
        menu_.addAction(copy_path_action)

        copy_name = ItemActions.CopyName(menu_, names, total)
        menu_.addAction(copy_name)

        copy_files = ItemActions.CopyObjects(menu_, total)
        copy_files.triggered.connect(lambda: self.setup_urls_to_copy(urls))
        menu_.addAction(copy_files)

        menu_.addSeparator()

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

        remove_objects = ItemActions.RemoveObjects(menu_, total)
        remove_objects.triggered.connect(lambda: self.remove_files_cmd(urls))
        menu_.addAction(remove_objects)  

        menu_.addSeparator()

        if Dynamic.urls_to_copy:
            paste_files = GridActions.PasteObjects(menu_, len(Dynamic.urls_to_copy))
            paste_files.triggered.connect(self.paste_files)
            menu_.addAction(paste_files)

        change_view = GridActions.ChangeViewMenu(menu_, self.view_index)
        change_view.change_view_sig.connect(self.change_view.emit)
        menu_.addMenu(change_view)

        upd_ = GridActions.UpdateGrid(menu_)
        upd_.triggered.connect(lambda: self.load_st_grid.emit())
        menu_.addAction(upd_)      

    def grid_context(self, menu_: UMenu, selected_path: str, urls: list[str], names: list[str], total: int):
        info = GridActions.Info(menu_)
        info.triggered.connect(lambda: self.win_info_cmd(selected_path))
        menu_.addAction(info)

        open_finder_action = GridActions.RevealInFinder(menu_, urls, total)
        menu_.addAction(open_finder_action)

        copy_path_action = GridActions.CopyPath(menu_, urls, total)
        menu_.addAction(copy_path_action)

        copy_name = GridActions.CopyName(menu_, names, total)
        menu_.addAction(copy_name)

        menu_.addSeparator()

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

        change_view = GridActions.ChangeViewMenu(menu_, self.view_index)
        change_view.change_view_sig.connect(self.change_view.emit)
        menu_.addMenu(change_view)

        if Dynamic.urls_to_copy:
            paste_files = GridActions.PasteObjects(menu_, len(Dynamic.urls_to_copy))
            paste_files.triggered.connect(self.paste_files)
            menu_.addAction(paste_files)

        upd_ = GridActions.UpdateGrid(menu_)
        upd_.triggered.connect(lambda: self.load_st_grid.emit())
        menu_.addAction(upd_)

    def paste_files(self):
        if not Dynamic.urls_to_copy:
            return

        # пресекаем попытку вставить файлы в место откуда скопированы
        for i in Dynamic.urls_to_copy:
            if os.path.dirname(i) == self.main_win_item.main_dir:
                return

        self.win_copy = CopyFilesWin(self.main_win_item.main_dir, Dynamic.urls_to_copy)
        self.win_copy.finished_.connect(lambda urls: self.paste_files_fin(urls))
        self.win_copy.error_.connect(self.show_error_win)
        self.win_copy.center(self.window())
        self.win_copy.show()
        QTimer.singleShot(300, self.win_copy.raise_)

    def paste_files_fin(self, urls: list[str]):
        if urls:
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

    def setup_urls_to_copy(self, urls: list[str]):
        Dynamic.urls_to_copy.clear()
        for i in urls:
            Dynamic.urls_to_copy.append(i)

    def remove_files_cmd(self, urls: list[str]):
        self.rem_win = RemoveFilesWin(self.main_win_item, urls)
        self.rem_win.finished_.connect(lambda urls: self.load_st_grid.emit())
        self.rem_win.center(self.window())
        self.rem_win.show()

    def set_urls(self):
        """
        Из-за того, что сетка удаляется из MainWin по таймеру,
        нужно вызывать этот метод, чтобы .urls моментально обновились
        для обработки в следующей сетке
        """
        GridList.sizes = [self.columnWidth(i) for i in range(0, 4)]
        urls = [i for i in self.get_selected_urls()]
        self.main_win_item.set_urls(urls)

    def select_row(self, index: QModelIndex):
        self.setCurrentIndex(index)
        tags = QItemSelectionModel.Select | QItemSelectionModel.Rows
        self.selectionModel().select(index, tags)

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

        menu_.show_()

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

            elif a0.key() == Qt.Key.Key_C:
                urls = self.get_selected_urls()
                if urls:
                    self.setup_urls_to_copy(urls)

            elif a0.key() == Qt.Key.Key_V:
                if Dynamic.urls_to_copy:
                    self.paste_files()

        if a0.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if a0.key() == Qt.Key.Key_C:
                self.setup_urls_to_copy()

            elif a0.key() == Qt.Key.Key_V:
                if not self.is_grid_search:
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

        img_ = QPixmap(Static.COPY_FILES_PNG)
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