import os
import subprocess

from PyQt5.QtCore import QDir, QModelIndex, Qt
from PyQt5.QtGui import (QContextMenuEvent, QDragEnterEvent, QDropEvent,
                         QKeyEvent)
from PyQt5.QtWidgets import (QAbstractItemView, QFileSystemModel, QSplitter,
                             QTableView)

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
        self._model.setFilter(QDir.NoDotAndDotDot | QDir.AllEntries)

        self.setModel(self._model)
        self.setRootIndex(self._model.index(self.main_win_item.main_dir))

        self.sortByColumn(GridList.col, GridList.order)
        for i in range(0, 4):
            self.setColumnWidth(i, GridList.sizes[i])
        self.loading_lbl.hide()

        self._model.directoryLoaded.connect(self.set_url_to_index_)

    def set_url_to_index_(self):
        root_index = self.rootIndex()
        rows = self._model.rowCount(root_index)

        for row in range(rows):
            index = self._model.index(row, 0, root_index)
            path = self._model.filePath(index)
            self.url_to_index[path] = index

        self.path_bar_update.emit(self.main_win_item.main_dir)
        self.sort_bar_update.emit(rows)

        for url, index in self.url_to_index.items():
            if url in self.main_win_item.urls:
                self.selectRow(index.row())
        self.main_win_item.urls.clear()

    def select_path(self, path: str):
        index = self._model.index(path, 0)
        self.setCurrentIndex(index)

    def set_first_col_width(self):
        left_menu_w = self.window().findChild(QSplitter).sizes()[0]
        win_w = self.window().width()
        columns_w = sum(GridList.sizes[1:])
        new_w = win_w - left_menu_w - columns_w - 30
        self.setColumnWidth(0, new_w)

    def double_clicked(self, index):
        path = self._model.filePath(index)
        self.view_cmd(path)

    def view_cmd(self, path: str):
        if os.path.isdir(path):
            self.main_win_item.main_dir = path
            self.load_st_grid_sig.emit()

        elif path.endswith(Static.ext_all):
            from .img_view_win import ImgViewWin

            url_to_wid = {
                url: Thumb(url)
                for url, index in self.url_to_index.items()
                if url.endswith(Static.ext_all)
            }

            cmd = lambda path: self.select_path(path)
            self.img_view_win = ImgViewWin(path, url_to_wid)
            self.img_view_win.move_to_url_sig.connect(cmd)
            self.img_view_win.center(self.window())
            self.img_view_win.show()

        else:
            subprocess.Popen(["open", path])

    def save_sort_settings(self, index):
        GridList.col = index
        GridList.order = self.horizontalHeader().sortIndicatorOrder()
        self.sortByColumn(GridList.col, GridList.order)

    def rearrange(self, *args, **kwargs):
        ...

    def sort_(self, *args, **kwargs):
        ...

    def filter_(self, *args, **kwargs):
        ...

    def resize_(self, *args, **kwargs):
        ...

    def select_new_widget(self, *args, **kwargs):
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
        view_ = ItemActions.View(menu_)
        view_.triggered.connect(lambda: self.view_cmd(selected_path))
        menu_.addAction(view_)

        if os.path.isdir(selected_path):
            new_window = ItemActions.OpenInNewWindow(menu_)
            cmd_ = lambda: self.open_in_new_window.emit(selected_path)
            new_window.triggered.connect(cmd_)
            menu_.addAction(new_window)
        else:
            open_menu = ItemActions.OpenInApp(menu_, selected_path)
            menu_.addMenu(open_menu)

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
                cmd_ = lambda: self.fav_cmd_sig.emit(("del", selected_path))
                fav_action = ItemActions.FavRemove(menu_)
                fav_action.triggered.connect(cmd_)
                menu_.addAction(fav_action)
            else:
                cmd_ = lambda: self.fav_cmd_sig.emit(("add", selected_path))
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

        upd_ = GridActions.UpdateGrid(menu_)
        upd_.triggered.connect(lambda: self.load_st_grid_sig.emit())
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
                cmd_ = lambda: self.fav_cmd_sig.emit(("del", selected_path))
                fav_action = GridActions.FavRemove(menu_)
                fav_action.triggered.connect(cmd_)
                menu_.addAction(fav_action)
            else:
                cmd_ = lambda: self.fav_cmd_sig.emit(("add", selected_path))
                fav_action = GridActions.FavAdd(menu_)
                fav_action.triggered.connect(cmd_)
                menu_.addAction(fav_action)

        menu_.addSeparator()

        change_view = GridActions.ChangeViewMenu(menu_, self.view_index)
        change_view.change_view_sig.connect(self.change_view_sig.emit)
        menu_.addMenu(change_view)

        if Dynamic.urls_to_copy:
            paste_files = GridActions.PasteObjects(menu_, len(Dynamic.urls_to_copy))
            paste_files.triggered.connect(self.paste_files)
            menu_.addAction(paste_files)

        upd_ = GridActions.UpdateGrid(menu_)
        upd_.triggered.connect(lambda: self.load_st_grid_sig.emit())
        menu_.addAction(upd_)

    def paste_files(self):
        if not Dynamic.urls_to_copy:
            return

        # пресекаем попытку вставить файлы в место откуда скопированы
        for i in Dynamic.urls_to_copy:
            if os.path.dirname(i) == self.main_win_item.main_dir:
                return

        self.win_copy = CopyFilesWin(self.main_win_item, Dynamic.urls_to_copy)
        self.win_copy.finished_.connect(lambda urls: self.paste_files_fin(urls))
        self.win_copy.error_win_sig.connect(self.error_win_cmd)
        self.win_copy.center(self.window())
        self.win_copy.show()

    def paste_files_fin(self, urls: list[str]):
        self.load_st_grid_sig.emit()
        Dynamic.urls_to_copy.clear()

    def error_win_cmd(self):
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
        self.rem_win.finished_.connect(lambda urls: self.load_st_grid_sig.emit())
        self.rem_win.center(self.window())
        self.rem_win.show()

    def deleteLater(self):
        GridList.sizes = [self.columnWidth(i) for i in range(0, 4)]
        for i in self.get_selected_urls():
            self.main_win_item.urls.append(i)
        super().deleteLater()

    def contextMenuEvent(self, event: QContextMenuEvent):
        # определяем выделена ли строка
        index = self.indexAt(event.pos())
        selected_path = self._model.filePath(index)

        menu_ = UMenu(parent=self)

        if selected_path:
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
                root = os.path.dirname(self.main_win_item.main_dir)
                if root != os.sep:
                    self.new_history_item.emit(root)
                    self.main_win_item.main_dir = root
                    self.load_st_grid_sig.emit()
                    # return

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

        elif a0.key() in (Qt.Key.Key_Return, Qt.Key.Key_Space):
            index = self.currentIndex()
            self.double_clicked(index)
            # return

        return super().keyPressEvent(a0)

    def dragEnterEvent(self, a0: QDragEnterEvent):
        if a0.mimeData().hasUrls():
            a0.acceptProposedAction()
        return super().dragEnterEvent(a0)
    
    def dropEvent(self, a0: QDropEvent):
        Dynamic.urls_to_copy.clear()
        Dynamic.urls_to_copy = [i.toLocalFile() for i in a0.mimeData().urls()]

        main_dir_ = Utils.normalize_slash(self.main_win_item.main_dir)
        main_dir_ = Utils.add_system_volume(main_dir_)
        for i in Dynamic.urls_to_copy:
            i = Utils.normalize_slash(i)
            i = Utils.add_system_volume(i)
            if os.path.commonpath([i, main_dir_]) == main_dir_:
                print("Нельзя копировать в себя")
                return

        if Dynamic.urls_to_copy:
            self.paste_files()

        return super().dropEvent(a0)