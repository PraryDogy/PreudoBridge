import os

from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtGui import QDropEvent, QIcon
from PyQt5.QtWidgets import QListWidget, QListWidgetItem

from cfg import JsonData, Static
from system.items import ContextItem, MainWinItem, RemoveItem, RenameItem

from ._base_widgets import UMenu
from .actions import CommonActions, FavActions, ThumbActions


class FavItemBase(QListWidgetItem):
    hh = 30

    def __init__(self, name: str, src: str, main_win_item: MainWinItem, parent: QListWidget):
        super().__init__()
        self.setSizeHint(QSize(parent.width(), self.hh))
        self.setText(name)

        self.main_win_item = main_win_item
        self.name = name
        self.src = src


class FavItemNew(FavItemBase):
    def __init__(self, name, src, main_win_item, parent):
        super().__init__(name, src, main_win_item, parent)


class FavItemPin(FavItemBase):
    def __init__(self, name, src, main_win_item, parent):
        super().__init__(name, src, main_win_item, parent)


class FavItemSpacer(QListWidgetItem):
    hh = 10
    def __init__(self, parent: QListWidget):
        super().__init__()
        self.setSizeHint(QSize(parent.width(), self.hh))
        self.setFlags(Qt.ItemFlag.NoItemFlags)


class MenuFavs(QListWidget):
    # new_history_item = pyqtSignal(str)
    load_st_grid = pyqtSignal(str)
    new_main_win = pyqtSignal(str)
    reveal = pyqtSignal(list)
    copy_urls = pyqtSignal(list)
    copy_names = pyqtSignal(list)

    rename_fav = pyqtSignal(RenameItem)
    remove_fav = pyqtSignal(RemoveItem)

    folder_icon: QIcon
    folder_pin_icon: QIcon

    def __init__(self, main_win_item: MainWinItem):
        super().__init__()
        self.main_win_item = main_win_item
        self.url_to_item: dict[str, QListWidgetItem] = {}

        self.horizontalScrollBar().setDisabled(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.setAcceptDrops(True)
        self.create_icons()
        self.init_ui()

    def create_icons(self):
        folder = os.path.join(Static.internal_images_dir, "folder.png")
        folder_pin = os.path.join(Static.internal_images_dir, "folder_pin.png")
        self.folder_icon = QIcon(folder)
        self.folder_pin_icon = QIcon(folder_pin)

    def init_ui(self):
        self.clear()
        self.url_to_item.clear()

        user = os.path.expanduser("~")
        icloud = "Library/Mobile Documents/com~apple~CloudDocs"
        fav_pin = {
            "/Volumes": "Компьютер",
            os.path.join(user, icloud): "iCloud Drive",
            os.path.join(user, "Desktop"): "Рабочий стол",
            os.path.join(user, "Downloads"): "Загрузки"
        }

        for src, name in fav_pin.items():
            list_item = FavItemPin(name, src, self.main_win_item, self)
            list_item.setIcon(self.folder_pin_icon)
            self.addItem(list_item)
            self.url_to_item[src] = list_item

            if self.main_win_item.abs_current_dir == src:
                self.setCurrentItem(list_item)

        item = FavItemSpacer(self)
        self.addItem(item)

        for src, name in JsonData.favs.items():
            list_item = FavItemNew(name, src, self.main_win_item, self)
            list_item.setIcon(self.folder_icon)
            self.addItem(list_item)
            self.url_to_item[src] = list_item

            if self.main_win_item.abs_current_dir == src:
                self.setCurrentItem(list_item)

    def select_fav(self, src: str):
        self.clearSelection()
        if src in self.url_to_item:
            self.setCurrentItem(self.url_to_item[src])
    
    def add_fav_cmd(self, path: str, text: str):

        JsonData.favs[path] = text
        JsonData.write_json_data()
        
        list_item = FavItemNew(text, path, self.main_win_item, self)
        list_item.setIcon(self.folder_icon)
        self.addItem(list_item)
        self.url_to_item[path] = list_item

    def rename_fav_cmd(self, fav_item: FavItemBase):

        def finished(text: str):
            JsonData.favs[fav_item.src] = text
            JsonData.write_json_data()
            fav_item.setText(text)
            fav_item.name = text

        item = RenameItem(
            text=fav_item.name,
            callback=lambda new_name: finished(new_name)
        )
        self.rename_fav.emit(item)

    def remove_fav_cmd(self, fav_item: FavItemBase):

        def finished():
            JsonData.favs.pop(fav_item.src)
            JsonData.write_json_data()
            self.takeItem(self.row(fav_item))

        item = RemoveItem(
            urls=[fav_item.src, ],
            callback=lambda: finished()
        )
        self.remove_fav.emit(item)
    
    def contextMenuEvent(self, a0):
        fav_item: FavItemBase = self.itemAt(a0.pos())
        if not fav_item:
            return

        urls = [fav_item.src, ]
        item = ContextItem(
            main_win_item=self.main_win_item,
            urls=urls,
            data_items=list()
        )
        menu = UMenu(parent=self)
        thumb_actions = ThumbActions(menu, item)
        fav_action = FavActions(menu, item)
        common_actions = CommonActions(menu, item)

        menu.add_action(
            action=thumb_actions.open_thumb,
            cmd=lambda: self.load_st_grid.emit(urls[0])
        )
        menu.add_action(
            action=thumb_actions.new_main_win,
            cmd=lambda: self.new_main_win.emit(urls[0])
        )
        menu.addSeparator()
        menu.add_action(
            common_actions.reveal,
            cmd=lambda: self.reveal.emit(urls)
        )
        menu.add_action(
            common_actions.copy_path,
            cmd=lambda: self.copy_urls.emit(urls)
        )
        menu.add_action(
            common_actions.copy_name,
            cmd=lambda: self.copy_names.emit(urls)
        )
        if isinstance(fav_item, FavItemNew):
            menu.addSeparator()
            menu.add_action(
                action=thumb_actions.rename,
                cmd=lambda: self.rename_fav_cmd(fav_item)
            )
            menu.add_action(
                action=fav_action.fav_remove,
                cmd=lambda: self.remove_fav_cmd(fav_item)
            )
        menu.show_under_cursor()
        return super().contextMenuEvent(a0)
    
    def mouseReleaseEvent(self, e):
        item: FavItemBase = self.itemAt(e.pos())
        if item:
            self.load_st_grid.emit(item.src)
        else:
            self.clearSelection()
        return super().mouseReleaseEvent(e)

    def dragMoveEvent(self, e):
        index = self.indexAt(e.pos()).row()
        if 0 < index < 5:
            e.ignore()
        else:
            super().dragMoveEvent(e)

    def dragEnterEvent(self, e):
        e.acceptProposedAction()
    
    def dropEvent(self, a0: QDropEvent | None) -> None:        
        urls = a0.mimeData().urls()
        if not urls:
            super().dropEvent(a0)
            new_order = {}
            for i in range(self.count()):
                fav_item = self.item(i)
                if isinstance(fav_item, FavItemNew):
                    new_order[fav_item.src] = fav_item.name
                else:
                    continue
            if new_order:
                JsonData.favs = new_order
                JsonData.write_json_data()
        else:
            url_ = urls[-1].toLocalFile()
            url_ = url_.rstrip(os.sep)
            if os.path.isdir(url_) and url_ not in JsonData.favs:
                print(123)
                item = RenameItem(
                    text=os.path.basename(url_),
                    callback=lambda text: self.add_fav_cmd(url_, text)
                )
                self.rename_fav.emit(item)
