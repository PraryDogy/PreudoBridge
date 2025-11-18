import gc
import inspect
import os
import sys

from PyQt5.QtCore import (QDateTime, QDir, QItemSelectionModel, QMimeData,
                          QModelIndex, Qt, QTimer, QUrl, pyqtSignal)
from PyQt5.QtGui import (QContextMenuEvent, QDrag, QDragEnterEvent,
                         QDragMoveEvent, QDropEvent, QKeyEvent, QPixmap)
from PyQt5.QtWidgets import (QAbstractItemView, QApplication, QFileSystemModel,
                             QLabel, QSplitter, QTableView)

from cfg import Dynamic, JsonData, Static
from system.items import BaseItem, CopyItem, MainWinItem
from system.shared_utils import SharedUtils
from system.utils import Utils

from ._base_widgets import UMenu
from .actions import GridActions, ItemActions
# main win
from .archive_win import ArchiveWin
from .copy_files_win import CopyFilesWin, ErrorWin
from .grid import Thumb
from .img_convert_win import ImgConvertWin
from .remove_files_win import RemoveFilesWin
from .rename_win import RenameWin


class MyFileSystemModel(QFileSystemModel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cut_rows = set()

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            headers = ["Имя", "Размер", "Тип", "Дата изменения"]
            if 0 <= section < len(headers):
                return headers[section]
        return super().headerData(section, orientation, role)

    def flags(self, index):
        f = super().flags(index)
        if self.filePath(index) in self.cut_rows:
            return f & ~Qt.ItemFlag.ItemIsEnabled
        return f

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


class TableView(QTableView):
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
    download_cache = pyqtSignal(list)
    info_win = pyqtSignal(list)
    img_view_win = pyqtSignal(dict)

    not_exists_text = "Такой папки не существует. \nВозможно не подключен сетевой диск."
    empty_text = "Нет файлов"
    new_folder_text = "Новая папка"

    def __init__(self, main_win_item: MainWinItem):
        super().__init__()

        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDropIndicatorShown(True)

        self.main_win_item = main_win_item
        self.url_to_index: dict[str, QModelIndex] = {}
        self.main_win_item = main_win_item

        self.setSelectionBehavior(QTableView.SelectRows)
        self.setSortingEnabled(True)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().sectionClicked.connect(self.save_sort_settings)
        self.doubleClicked.connect(self.double_clicked)

        self._model = MyFileSystemModel()
        self._model.setFilter(QDir.AllEntries | QDir.NoDotAndDotDot)
        if JsonData.show_hidden:
            self._model.setFilter(self._model.filter() | QDir.Hidden)

        if os.path.exists(self.main_win_item.main_dir):
            self.setModel(self._model)
            self._model.setRootPath(self.main_win_item.main_dir)
            self.setRootIndex(self._model.index(self.main_win_item.main_dir))
        else:
            self.setModel(None)
            no_images = QLabel(self.not_exists_text, parent=self)
            no_images.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_images.move(
                (self.width() - no_images.width()) // 2,
                (self.height() - no_images.height()) // 2,
            )
            no_images.show()
            return

        self.sortByColumn(TableView.col, TableView.order)
        for i in range(0, 4):
            self.setColumnWidth(i, TableView.sizes[i])

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
        self.show()
        self.finished_.emit()

        if row_count == 0:
            self.no_files = QLabel(self.empty_text, parent=self)
            self.no_files.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.no_files.move(
                (self.width() - self.no_files.width()) // 2,
                (self.height() - self.no_files.height()) // 2,
            )
            self.no_files.show()

    def select_path(self, path: str):
        index = self._model.index(path, 0)
        self.select_row(index)

    def set_first_col_width(self):
        left_menu_w = self.window().findChild(QSplitter).sizes()[0]
        win_w = self.window().width()
        columns_w = sum(TableView.sizes[1:])
        new_w = win_w - left_menu_w - columns_w - 30
        self.setColumnWidth(0, new_w)

    def double_clicked(self, index):
        self.open_thumb(self.get_selected_urls())

    def new_folder(self):
        def fin(name: str):
            dest = os.path.join(self.main_win_item.main_dir, name)
            try:
                os.mkdir(dest)
                QTimer.singleShot(100, lambda: self.select_path(dest))
            except Exception as e:
                Utils.print_error()
        self.rename_win = RenameWin(self.new_folder_text)
        self.rename_win.center(self.window())
        self.rename_win.finished_.connect(lambda name: fin(name))
        self.rename_win.show()

    def open_thumb(self, urls: list[str]):
        if len(urls) == 1:
            if urls[0].endswith(Static.img_exts):
                url_to_wid = {
                    url: Thumb(url)
                    for url, v in self.url_to_index.items()
                    if url.endswith(Static.img_exts)
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
                if url.endswith(Static.img_exts)
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
                if not i.endswith(Static.img_exts)
                and
                os.path.isfile(i)
            ]

            for i in files:
                Utils.open_in_def_app(i)

    def open_img_view(self, start_url: str, url_to_wid: dict, is_selection: bool):
        self.img_view_win.emit({
            "start_url": start_url,
            "url_to_wid": url_to_wid,
            "is_selection": is_selection
        })

    def save_sort_settings(self, index):
        TableView.col = index
        TableView.order = self.horizontalHeader().sortIndicatorOrder()
        self.sortByColumn(TableView.col, TableView.order)

    def toggle_is_cut(self, value: bool):
        Dynamic.is_cut = value

    def open_win_info(self, src_list: list[str]):
        """
        Открыть окно информации о файле / папке
        """
        base_items = []
        for i in src_list:
            base_item = BaseItem(i)
            base_item.set_properties()
            base_items.append(base_item)
        self.info_win.emit(base_items)

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

        urls = [i for i in urls if i.endswith(Static.img_exts)]
        self.convert_win = ImgConvertWin(urls)
        self.convert_win.center(self.window())
        self.convert_win.finished_.connect(lambda urls: finished_(urls))
        self.convert_win.show()

    def make_archive(self, urls: list[str]):

        def archive_fin(url: str):
            try:
                self.archive_win = None
                gc.collect()
                QTimer.singleShot(300, lambda: self.select_path(url))
            except RuntimeError as e:
                ...

        def rename_fin(text: str):
            zip_path = os.path.join(self.main_win_item.main_dir, text)
            self.archive_win = ArchiveWin(urls, zip_path)
            assert isinstance(self.archive_win, ArchiveWin)
            self.archive_win.center(self.window())
            self.archive_win.finished_.connect(lambda: archive_fin(zip_path))
            self.archive_win.show()
            QTimer.singleShot(100, lambda: self.archive_win.raise_())

        selected_urls = self.get_selected_urls()
        if len(selected_urls) == 1:
            text = os.path.basename(selected_urls[0])
            text, ext = os.path.splitext(text)
            text = f"{text}.zip"
        else:
            text = "Архив.zip"

        self.rename_win = RenameWin(text)
        self.rename_win.center(self.window())
        self.rename_win.finished_.connect(rename_fin)
        self.rename_win.show()

    # def make_archive(self, urls: list[str]):

    #     def finished(*args):
    #         QTimer.singleShot(300, lambda: self.select_path(zip_path))

    #     zip_path = os.path.join(self.main_win_item.main_dir, "Архив.zip")
    #     self.archive_win = ArchiveWin(urls, zip_path)
    #     self.archive_win.finished_.connect(finished)
    #     self.archive_win.center(self.window())
    #     self.archive_win.show()

    def rename_row(self, url: str):
        
        def finished(text: str):
            root = os.path.dirname(url)
            new_url = os.path.join(root, text)
            os.rename(url, new_url)
            QTimer.singleShot(500, lambda: self.select_path(new_url))

        self.rename_win = RenameWin(os.path.basename(url))
        self.rename_win.finished_.connect(lambda text: finished(text))
        self.rename_win.center(self.window())
        self.rename_win.show()

    def item_context(self, menu_: UMenu, selected_path: str, urls: list[str], names: list[str], total: int):
        urls = self.get_selected_urls()
        dirs = [i for i in urls if os.path.isdir(i)]

        view_action = ItemActions.OpenThumb(menu_)
        view_action.triggered.connect(lambda: self.open_thumb(urls))
        menu_.addAction(view_action)

        if os.path.isfile(selected_path):
            open_in_app = ItemActions.OpenInApp(menu_, urls)
            menu_.addMenu(open_in_app)

        info = ItemActions.Info(menu_)
        info.triggered.connect(
            lambda: self.open_win_info(urls)
        )
        menu_.addAction(info)

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

        if selected_path.endswith(Static.img_exts):
            convert_action = ItemActions.ImgConvert(menu_)
            convert_action.triggered.connect(lambda: self.open_img_convert_win(urls))
            menu_.addAction(convert_action)

        if os.path.isdir(selected_path):
            download_cache = ItemActions.DownloadCache(menu_)
            download_cache.triggered.connect(
                lambda: self.download_cache.emit(dirs)
            )
            menu_.addAction(download_cache)

        # archive = ItemActions.MakeArchive(menu_)
        # archive.triggered.connect(lambda: self.make_archive(urls))
        # menu_.addAction(archive)

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

        new_folder = GridActions.NewFolder(menu_)
        new_folder.triggered.connect(self.new_folder)
        menu_.addAction(new_folder)

        info = GridActions.Info(menu_)
        info.triggered.connect(
            lambda: self.open_win_info([selected_path, ])
        )
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

    def flags(self, index: QModelIndex):
        return Qt.ItemIsEnabled  # отключаем выбор/редактирование

    def setup_urls_to_copy(self, urls: list[str]):
        CopyItem.set_src(self.main_win_item.main_dir)
        CopyItem.set_is_search(False)
        CopyItem.urls.clear()
        # if CopyItem._is_cut:
        #     self.clearSelection()
        for i in urls:
            CopyItem.urls.append(i)
            # if CopyItem._is_cut:
            #     ind = self.url_to_index[i]
            #     self._model.cut_rows.add(i)
                # self._model.dataChanged.emit(ind, ind)

    def remove_files_cmd(self, urls: list[str]):
        self.rem_win = RemoveFilesWin(self.main_win_item, urls)
        self.rem_win.finished_.connect(lambda urls: self.load_st_grid.emit())
        self.rem_win.center(self.window())
        self.rem_win.show()

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
                urls = self.get_selected_urls()
                if not urls:
                    urls = [self.main_win_item.main_dir, ]
                self.open_win_info(urls)
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
        sys_vol = SharedUtils.get_sys_vol()
        urls = [
            i.toLocalFile().rstrip(os.sep)
            for i in a0.mimeData().urls()
        ]
        urls = [
            SharedUtils.add_sys_vol(i, sys_vol)
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

        img_ = QPixmap(os.path.join(Static.app_icons_dir, "files.svg"))
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
