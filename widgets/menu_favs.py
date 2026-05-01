import os

from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtGui import QDropEvent, QIcon
from PyQt5.QtWidgets import QListWidget, QListWidgetItem

from cfg import JsonData, Static
from system.items import MainWinItem, NameUrlItem

from ._base_widgets import UMenu
from .actions import Actions


class ListItemBase(QListWidgetItem):
    hh = 30

    def __init__(self, name: str, src: str, main_win_item: MainWinItem, parent: QListWidget):
        super().__init__()
        self.setSizeHint(QSize(parent.width(), self.hh))
        self.setText(name)

        self.main_win_item = main_win_item
        self.name = name
        self.src = src


class ListItem(ListItemBase):
    def __init__(self, name, src, main_win_item, parent):
        super().__init__(name, src, main_win_item, parent)


class ListItemPin(ListItemBase):
    def __init__(self, name, src, main_win_item, parent):
        super().__init__(name, src, main_win_item, parent)
        self.setFlags(self.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)


class ListItemSpacer(QListWidgetItem):
    hh = 10
    def __init__(self, parent: QListWidget):
        super().__init__()
        self.setSizeHint(QSize(parent.width(), self.hh))
        self.setFlags(Qt.ItemFlag.NoItemFlags)


class MenuFavs(QListWidget):
    history_item = pyqtSignal(str)
    load_st_grid = pyqtSignal(str)
    new_main_win = pyqtSignal(str)
    reveal_urls = pyqtSignal(list)
    copy_urls = pyqtSignal(list)
    copy_names = pyqtSignal(list)
    rename_fav = pyqtSignal(NameUrlItem)
    remove_fav = pyqtSignal(str)
    new_fav = pyqtSignal(NameUrlItem)
    info = pyqtSignal(NameUrlItem)
    folder_icon: QIcon
    folder_pin_icon: QIcon

    def __init__(self, main_win_item: MainWinItem):
        super().__init__()
        self.main_win_item = main_win_item
        self.url_to_item: dict[str, ListItemBase] = {}

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
            list_item = ListItemPin(name, src, self.main_win_item, self)
            list_item.setIcon(self.folder_pin_icon)
            self.addItem(list_item)
            self.url_to_item[src] = list_item

            if self.main_win_item.abs_current_dir == src:
                self.setCurrentItem(list_item)

        item = ListItemSpacer(self)
        self.addItem(item)

        for src, name in JsonData.favs.items():
            list_item = ListItem(name, src, self.main_win_item, self)
            list_item.setIcon(self.folder_icon)
            self.addItem(list_item)
            self.url_to_item[src] = list_item

            if self.main_win_item.abs_current_dir == src:
                self.setCurrentItem(list_item)

    def select_fav(self, src: str):
        self.clearSelection()
        if src in self.url_to_item:
            self.setCurrentItem(self.url_to_item[src])
    
    def add_fav_cmd(self, fav_item: NameUrlItem):
        JsonData.favs[fav_item.url] = fav_item.name
        JsonData.write_json_data()
        list_item = ListItem(fav_item.name, fav_item.url, self.main_win_item, self)
        list_item.setIcon(self.folder_icon)
        self.addItem(list_item)
        self.url_to_item[fav_item.url] = list_item

    def rename_fav_finalize(self, fav_item: NameUrlItem):
        item = self.url_to_item[fav_item.url]
        JsonData.favs[fav_item.url] = fav_item.name
        JsonData.write_json_data()
        item.setText(fav_item.name)
        item.name = fav_item.name

    def remove_fav_finalize(self, url: str):
        list_item = self.url_to_item[url]
        JsonData.favs.pop(url)
        JsonData.write_json_data()
        self.takeItem(self.row(list_item))

    def open_fav_cmd(self, path: str):
        self.history_item.emit(path)
        self.load_st_grid.emit(path)
    
    def contextMenuEvent(self, a0):
        list_item: ListItemBase = self.itemAt(a0.pos())
        if not list_item or isinstance(list_item, ListItemSpacer):
            return

        urls = [list_item.src, ]
        name_path_item = NameUrlItem(
            name=list_item.name,
            url=list_item.src
        )
        context_menu = UMenu(parent=self)
        context_actions = Actions(context_menu)

        context_menu.add_action(
            action=context_actions.open_thumb,
            callback=lambda: self.open_fav_cmd(list_item.src)
        )
        context_menu.add_action(
            action=context_actions.new_main_win,
            callback=lambda: self.new_main_win.emit(list_item.src)
        )
        context_menu.addSeparator()
        context_menu.add_action(
            context_actions.win_info,
            callback=lambda: self.info.emit(name_path_item)
        )
        context_menu.add_action(
            context_actions.reveal,
            callback=lambda: self.reveal_urls.emit(urls)
        )
        context_menu.addSeparator()
        context_menu.add_action(
            context_actions.copy_path,
            callback=lambda: self.copy_urls.emit(urls)
        )
        context_menu.add_action(
            context_actions.copy_name,
            callback=lambda: self.copy_names.emit(urls)
        )
        if isinstance(list_item, ListItem):
            context_menu.addSeparator()
            context_menu.add_action(
                action=context_actions.rename,
                callback=lambda: self.rename_fav.emit(name_path_item)
            )
            context_menu.add_action(
                action=context_actions.fav_remove,
                callback=lambda: self.remove_fav.emit(list_item.src)
            )
        context_menu.show_under_mouse()
        return super().contextMenuEvent(a0)
    
    def mouseReleaseEvent(self, e):
        item: ListItemBase = self.itemAt(e.pos())
        if isinstance(item, ListItemSpacer):
            return
        if item:
            if e.modifiers() == Qt.KeyboardModifier.ControlModifier:
                self.new_main_win.emit(item.src)
            else:
                self.open_fav_cmd(item.src)
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
                list_item = self.item(i)
                if isinstance(list_item, ListItem):
                    new_order[list_item.src] = list_item.name
                else:
                    continue
            if new_order:
                JsonData.favs = new_order
                JsonData.write_json_data()
        else:
            url_ = urls[-1].toLocalFile()
            url_ = url_.rstrip(os.sep)
            if os.path.isdir(url_):
                fav_item = NameUrlItem(
                    name=os.path.basename(url_),
                    url=url_
                )
                self.new_fav.emit(fav_item)
