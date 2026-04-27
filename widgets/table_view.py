import os

from PyQt5.QtCore import (QDateTime, QDir, QItemSelectionModel, QMimeData,
                          QModelIndex, Qt, QTimer, QUrl, pyqtSignal)
from PyQt5.QtGui import (QContextMenuEvent, QDrag, QDragEnterEvent,
                         QDragMoveEvent, QDropEvent, QImage, QKeyEvent,
                         QPixmap)
from PyQt5.QtWidgets import (QAbstractItemView, QApplication, QFileSystemModel,
                             QLabel, QSplitter, QTableView)

from cfg import Dynamic, JsonData, Static
from system.items import (ClipboardItemGlob, ContextItem, DataItem,
                          ImgViewItem, MainWinItem, RemoveItem, RenameItem,
                          TotalCountItem)
from system.shared_utils import ImgUtils
from system.utils import Utils

from ._base_widgets import UMenu
from .actions import CommonActions, GridActions, ThumbActions
# main win
from .grid import Thumb


class MyFileSystemModel(QFileSystemModel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        exts = [
            f"*{ext}"
            for ext in ImgUtils.ext_all
        ]
        self.setNameFilters(exts)
        self.setNameFilterDisables(False) 
        self.setFilter(
            QDir.Filter.Files | 
            QDir.Filter.AllDirs | 
            QDir.Filter.NoDotAndDotDot
        )
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
    bar_path_update = pyqtSignal(str)
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

    reveal_urls = pyqtSignal(list)
    copy_urls = pyqtSignal(list)
    copy_names = pyqtSignal(list)
    img_convert_win = pyqtSignal(list)

    open_in_app = pyqtSignal(tuple)
    remove_files = pyqtSignal(RemoveItem)
    rename_file = pyqtSignal(RenameItem)
    new_folder = pyqtSignal()

    files_icon = Utils.scaled(
        qimage=QImage(os.path.join(Static.internal_images_dir, "files.png")),
        size=64
    )

    not_exists_text = "Такой папки не существует. \nВозможно не подключен сетевой диск."
    empty_text = "Нет файлов"

    def __init__(self, main_win_item: MainWinItem):
        super().__init__()

        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDropIndicatorShown(True)

        # Заглушка (placeholder) для grid_wid. 
        # Используется для предотвращения ошибок при вызове .hide() в MainWin.
        self.grid_wid = QLabel()

        self.main_win_item = main_win_item
        self.url_to_index: dict[str, QModelIndex] = {}
        self.url_to_item: dict[str, DataItem] = {}
        self.main_win_item = main_win_item

        self.setSelectionBehavior(QTableView.SelectRows)
        self.setSortingEnabled(True)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().sectionClicked.connect(self.save_sort_settings)
        self.doubleClicked.connect(self.double_clicked)

        self._model = MyFileSystemModel()
        # self._model.setFilter(QDir.AllEntries | QDir.NoDotAndDotDot)
        # if JsonData.show_hidden:
            # self._model.setFilter(self._model.filter() | QDir.Hidden)

        if main_win_item.abs_current_dir is not None:
            self.setModel(self._model)
            self._model.setRootPath(self.main_win_item.abs_current_dir)
            self.setRootIndex(self._model.index(self.main_win_item.abs_current_dir))
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

            item = DataItem(path)
            item.set_properties()
            self.url_to_item[path] = item

        if self.main_win_item.go_to_widget:
            self.main_win_item.urls_to_select.append(
                self.main_win_item.go_to_widget
            )
            self.main_win_item.go_to_widget = ""
        for url in self.main_win_item.urls_to_select:
            if url in self.url_to_index:
                index = self.url_to_index.get(url)
                self.select_row(index)
        QTimer.singleShot(100, lambda: self.verticalScrollBar().setValue(0))

        self.setCurrentIndex(QModelIndex())
        self.bar_path_update.emit(self.main_win_item.abs_current_dir)
        self.load_finished.emit()

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

    def open_thumb(self, urls: list[str]):
        if len(urls) == 1:
            data_item = DataItem(urls[0])
            data_item.set_properties()
            thumb = Thumb(data_item)
            if data_item.type_ == Static.folder_type:
                self.new_history_item.emit(data_item.abs_path)
                self.load_st_grid.emit(data_item.abs_path)
            else:
                url_to_wid = {}
                for url, _ in self.url_to_index.items():
                    if url.endswith(ImgUtils.ext_all):
                        data = DataItem(url)
                        data.set_properties()
                        url_to_wid[url] = Thumb(data)

                if url_to_wid:
                    item = ImgViewItem(
                        start_url=urls[0],
                        url_to_wid=url_to_wid,
                        is_selection=False
                    )
                    self.img_view_win.emit(item)
        else:
            url_to_wid = {}
            for url in self.get_selected_urls():
                if url.endswith(ImgUtils.ext_all):
                    data = DataItem(url)
                    data.set_properties()
                    thumb = Thumb(data)
                    url_to_wid[url] = thumb
            item = ImgViewItem(
                start_url=list(url_to_wid)[0],
                url_to_wid=url_to_wid,
                is_selection=True
            )
            self.img_view_win.emit(item)

    def save_sort_settings(self, index):
        TableView.col = index
        TableView.order = self.horizontalHeader().sortIndicatorOrder()
        self.sortByColumn(TableView.col, TableView.order)

    def toggle_is_cut(self, value: bool):
        Dynamic.is_cut = value

    def open_win_info_cmd(self, src_list: list[str]):
        """
        Открыть окно информации о файле / папке
        """
        data_items = []
        for i in src_list:
            data_item = DataItem(i)
            data_item.set_properties()
            data_items.append(data_item)
        self.open_win_info.emit(data_items)

    def get_selected_urls(self):
        urls = []
        selection_model = self.selectionModel()
        selected_rows = selection_model.selectedRows()
        for index in selected_rows:
            file_path = self._model.filePath(index)  # Получаем путь по индексу
            urls.append(file_path)
        return urls

    def open_img_convert_win(self, urls: list[str]):
        urls = [i for i in urls if i.endswith(ImgUtils.ext_all)]
        self.img_convert_win.emit(urls)

    # def flags(self, index: QModelIndex):
        # return Qt.ItemIsEnabled 

    def setup_clipboard(self, urls: list[str], is_cut: bool):
        ClipboardItemGlob.src_dir = self.main_win_item.abs_current_dir
        ClipboardItemGlob.set_is_cut(is_cut)
        ClipboardItemGlob.src_urls.clear()
        for i in urls:
            ClipboardItemGlob.src_urls.append(i)

    def select_row(self, index: QModelIndex):
        self.setCurrentIndex(index)
        tags = QItemSelectionModel.Select | QItemSelectionModel.Rows
        self.selectionModel().select(index, tags)

    def remove_files_cmd(self, urls: list[str]):
        item = RemoveItem(
            item_type="filename",
            urls=urls,
            callback=None
        )
        self.remove_files.emit(item)

    def rename_file_cmd(self, filepath: str):
        item = RenameItem(
            item_type="filename",
            filepath=filepath,
            callback=None
        )
        self.rename_file.emit(item)

    def folder_actions(self, menu_: UMenu, item: ContextItem, path: str):
        actions = ThumbActions(menu_, item)

        menu_.add_action(
            action=actions.new_main_win,
            cmd=lambda: self.new_main_win_open.emit(path)
        )
        if path in JsonData.favs:
            menu_.add_action(
                action=actions.fav_remove,
                cmd=lambda: self.fav_cmd(-1, path)
            )
        else:
            menu_.add_action(
                action=actions.fav_add,
                cmd=lambda: self.fav_cmd(1, path)
            )

    def base_thumb_actions(self, menu: UMenu, item: ContextItem, path: str):
        actions = ThumbActions(menu, item)
        common_actions = CommonActions(menu, item)

        menu.add_action(
            action=actions.open_thumb,
            cmd=lambda: self.open_thumb(item.urls)
        )
        if not path.endswith(ImgUtils.ext_all):
            self.folder_actions(menu, item, path)
        else:
            menu.add_menu(
                menu=actions.open_in_app_menu,
                cmd=lambda app_path: self.open_in_app.emit((item.urls, app_path))
            )
            menu.add_action(
                action=actions.convert_to_jpg,
                cmd=lambda: self.open_img_convert_win(item.urls)
            )
        menu.addSeparator()
        menu.add_action(
            action=common_actions.win_info,
            cmd=lambda: self.open_win_info.emit(item.data_items)
        )
        menu.add_action(
            action=actions.rename,
            cmd=lambda: self.rename_file_cmd(path)
        )
        menu.add_action(
            action=common_actions.reveal,
            cmd=lambda: self.reveal_urls.emit(item.urls)
        )
        menu.addSeparator()
        menu.add_action(
            action=common_actions.copy_path,
            cmd=lambda: self.copy_urls.emit(item.urls)
        )
        menu.add_action(
            action=common_actions.copy_name,
            cmd=lambda: self.copy_names.emit(item.urls)
        )
        menu.addSeparator()
        menu.add_action(
            action=actions.cut_files,
            cmd=lambda: self.setup_clipboard(item.urls, True)
        )
        menu.add_action(
            action=actions.copy_files,
            cmd=lambda: self.setup_clipboard(item.urls, False)
        )
        menu.addSeparator()
        menu.add_action(
            action=actions.remove_files,
            cmd=lambda: self.remove_files_cmd(item.urls)
        )

    def base_grid_actions(self, menu: UMenu, item: ContextItem):
        actions = GridActions(menu, item)
        common_actions = CommonActions(menu, item)
        menu.add_action(
            action=actions.new_folder,
            cmd=lambda: self.new_folder.emit()
        )
        menu.add_action(
            action=actions.update_grid,
            cmd=lambda: self.load_st_grid.emit(self.main_win_item.abs_current_dir)
        )
        menu.add_action(
            action=common_actions.win_info,
            cmd=lambda: self.open_win_info.emit(item.data_items)
        )
        menu.add_action(
            action=common_actions.reveal,
            cmd=lambda: self.reveal_urls.emit(item.urls)
        )
        menu.addSeparator()
        menu.add_action(
            action=common_actions.copy_path,
            cmd=lambda: self.copy_urls.emit(item.urls)
            
        )
        menu.add_action(
            action=common_actions.copy_name,
            cmd=lambda: self.copy_names.emit(item.urls)
        )
        menu.addSeparator()
        menu.add_menu(
            menu=actions.change_view,
            cmd=lambda: self.change_view.emit()
        )
        if ClipboardItemGlob.src_dir:
            menu.addSeparator()
            menu.add_action(
                action=actions.paste_files,
                cmd=lambda: self.paste_files.emit()
            )

    def contextMenuEvent(self, event: QContextMenuEvent):
        # определяем выделена ли строка
        index = self.indexAt(event.pos())
        selected_path = self._model.filePath(index)
        item = ContextItem(
            main_win_item=self.main_win_item,
            urls=[],
            data_items=[]
        )
        menu_ = UMenu(parent=self)

        if index.isValid():
            item.urls = self.get_selected_urls()
            # если выделены другие строка но кликнутая не выделена
            # то выделяем только ее
            if selected_path not in item.urls:
                item.urls.clear()
                self.select_row(index)
                item.urls = self.get_selected_urls()
            item.data_items = [self.url_to_item[i] for i in item.urls]
            self.base_thumb_actions(menu_, item, selected_path)

        else:

            data_item = DataItem(self.main_win_item.abs_current_dir)
            data_item.set_properties()
            item.urls = [self.main_win_item.abs_current_dir, ]
            item.data_items = [data_item, ]
            self.base_grid_actions(menu_, item)

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
                    urls = [self.main_win_item.abs_current_dir, ]
                self.open_win_info_cmd(urls)
                # return

            elif a0.key() == Qt.Key.Key_Backspace:
                urls = self.get_selected_urls()
                if urls:
                    self.remove_files_cmd(urls)

            elif a0.key() == Qt.Key.Key_X:
                urls = self.get_selected_urls()
                if urls:
                    self.setup_clipboard(urls, True)

            elif a0.key() == Qt.Key.Key_C:
                urls = self.get_selected_urls()
                if urls:
                    self.setup_clipboard(urls, False)

            elif a0.key() == Qt.Key.Key_V:
                if ClipboardItemGlob.src_urls:
                    self.paste_files.emit()

        elif a0.key() in (Qt.Key.Key_Return, Qt.Key.Key_Space):
            if not a0.isAutoRepeat():
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
        urls = [
            i.toLocalFile().rstrip(os.sep)
            for i in a0.mimeData().urls()
        ]
        src = os.path.dirname(urls[0])
        if src == self.main_win_item.abs_current_dir:
            print("нельзя копировать в себя через DropEvent")
            return
        else:
            ClipboardItemGlob.src_dir = src
            ClipboardItemGlob.src_urls = urls
            self.paste_files.emit()
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

        img_ = QPixmap.fromImage(self.copy_files_icon)
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
        self.main_win_item.urls_to_select = urls
        return super().deleteLater()
    
    def close(self):
        urls = self.get_selected_urls()
        self.main_win_item.urls_to_select = urls
        return super().close()
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.model():
            total_width = self.viewport().width()
            other_width = sum(self.columnWidth(i) for i in range(1, self.model().columnCount()))
            self.setColumnWidth(0, total_width - other_width)
