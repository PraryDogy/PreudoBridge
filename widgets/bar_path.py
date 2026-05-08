import os

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QContextMenuEvent, QImage, QPixmap
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QWidget

from cfg import JsonData, Static
from system.items import DataItem, ImgViewItem, MainWinItem, NameUrlItem
from system.shared_utils import ImgUtils
from system.utils import Utils

from ._base_widgets import UMenu, BaseSignals
from .actions import Actions


class Icons:
    computer: QPixmap
    disk: QPixmap
    folder: QPixmap
    image: QPixmap


class PathItem(QWidget):
    min_wid = 5
    arrow_right = " \U0000203A" # ›
    item_height = 15

    def __init__(self, dir: str, name: str, main_win_item: MainWinItem):
        """
        Этот виджет - часть группы виджетов PathItem, которые в сумме отображают
        указанный путь  
        Например: /путь/до/файла.txt    
        Указанный путь будет разбит на секции, которые отображаются в виде PathItem     
        Мы получим группу виджетов PathItem (имя - путь),   
        где каждый видждет PathItem будет кликабельным и открывать соответсвующий путь  
        путь - /путь    
        до - /путь/до   
        файла.txt - /путь/до/файла.txt  
        """
        super().__init__()
        self.main_win_item = main_win_item
        self.setFixedHeight(PathItem.item_height)
        self.item_dir = dir

        item_layout = QHBoxLayout()
        item_layout.setContentsMargins(0, 0, 0, 0)
        item_layout.setSpacing(5)
        self.setLayout(item_layout)

        self.img_wid = QLabel()
        item_layout.addWidget(self.img_wid)
        
        self.text_wid = QLabel(text=name)
        self.collapse()
        item_layout.addWidget(self.text_wid)

    def set_icon(self, qpixmap: QPixmap):
        self.img_wid.setPixmap(qpixmap)

    def add_arrow(self):
        """
        Добавляет к тексту виджета ">"
        """
        t = self.text_wid.text() + " " + PathItem.arrow_right
        self.text_wid.setText(t)

    def del_arrow(self):
        """
        Удаляет ">"
        """
        t = self.text_wid.text().replace(PathItem.arrow_right, "")
        self.text_wid.setText(t)

    def expand(self):
        """
        Показывает виджет в полную длину
        """
        self.text_wid.setFixedWidth(self.text_wid.sizeHint().width())
 
    def solid_style(self):
        """
        Выделяет виджет синим цветом
        """
        self.text_wid.setStyleSheet(
            f"""
                background: {Static.rgba_blue};
                border-radius: 2px;
            """
        )

    def default_style(self):
        """
        Сбрасывает стиль
        """
        self.text_wid.setStyleSheet("")

    def collapse(self):
        """
        Схлопывает виджет до указанной минимальной длины, если
        виджет находится не под курсором мыши
        """
        if not self.text_wid.underMouse():
            self.text_wid.setMinimumWidth(self.min_wid)

    def enterEvent(self, a0):
        """
        Раскрывает виджет на всю его длину при наведении мыши
        """
        self.expand()

    def leaveEvent(self, a0):
        """
        Отложено схолпывает виджет до указанной минимальной длины
        """
        QTimer.singleShot(500, self.collapse)


class BarPath(QWidget):
    last_item_limit = 40
    bar_height = 25

    def __init__(self, main_win_item: MainWinItem):
        """
        Нижний бар:     
        - Группа виджетов PathItem (читай описание PathItem)  
        """
        super().__init__()
        self.setFixedHeight(BarPath.bar_height)
        self.setAcceptDrops(True)
        self.create_icons()

        self.base_signals = BaseSignals()
        self.main_win_item = main_win_item
        self.current_path: str = None

        self.main_lay = QHBoxLayout()
        self.main_lay.setContentsMargins(0, 0, 0, 0)
        self.main_lay.setSpacing(5)
        self.main_lay.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.setLayout(self.main_lay)
        self.update(self.main_win_item.abs_current_dir)

    def create_icons(self):
        icons = {
            "computer": "computer.png",
            "disk": "disk.png",
            "folder": "folder.png",
            "image": "image.png"
        }
        for attr, icon in icons.items():
            path = os.path.join(Static.internal_images_dir, icon)
            qimage = QImage(path)
            qimage = Utils.scaled(qimage, 15)
            setattr(Icons, attr, QPixmap.fromImage(qimage))

    def fav_cmd(self, offset: int, src: str):
        if offset == -1:
            self.base_signals.remove_fav.emit(src)
        else:
            item = NameUrlItem(
                name=os.path.basename(src),
                url=src
            )
            self.base_signals.new_fav.emit(item)

    def update(self, dir: str):
        """
        Отобразить новый путь сетки / папки / файла     
        src: путь сетки / папки / файла
        """
        if dir == self.current_path:
            return
        for i in self.findChildren(PathItem):
            i.deleteLater()
        self.current_path = dir
        root = dir.strip(os.sep).split(os.sep)
        path_items: dict[int, PathItem] = {}

        for x, name in enumerate(root, start=1):
            dir = os.path.join(os.sep, *root[:x])
            path_item = PathItem(dir, name, self.main_win_item)
            path_item.add_arrow()
            path_items[x] = path_item
            self.main_lay.addWidget(path_item)
            path_item.set_icon(Icons.folder)

        path_items.get(1).set_icon(Icons.computer)

        if len(path_items) >= 2:
            path_items.get(2).set_icon(Icons.disk)

        last_item = path_items.get(len(root))
        if dir.endswith(ImgUtils.ext_all):
            last_item.set_icon(Icons.image)

        text_ = last_item.text_wid.text()
        if len(text_) > BarPath.last_item_limit:
            path_item.text_wid.setText(text_[:BarPath.last_item_limit] + "...")

        last_item.del_arrow()
        last_item.expand()
        last_item.enterEvent = lambda *args, **kwargs: None
        last_item.leaveEvent = lambda *args, **kwargs: None

    def view_folder_cmd(self, path: str):
        self.base_signals.history_item.emit(path)
        self.base_signals.load_st_grid.emit(path)

    def view_image_cmd(self, path: str):
        data_item = DataItem(path)
        data_item.set_properties()
        url_to_data_item = {path: data_item, }
        item = ImgViewItem(
            current_url=path,
            url_to_data_item=url_to_data_item,
            is_selection=True
        )
        self.base_signals.img_view.emit(item)

    def contextMenuEvent(self, ev: QContextMenuEvent | None) -> None:
        wid: PathItem = self.childAt(ev.pos())
        if not isinstance(wid, (PathItem, QLabel)):
            return

        if isinstance(wid, QLabel):
            wid: PathItem = wid.parent()
            wid.solid_style()

        context_menu = UMenu()
        context_actions = Actions(context_menu)
        if self.current_path.endswith(ImgUtils.ext_all):
            urls = [self.current_path, ]
        else:
            urls = [self.main_win_item.abs_current_dir, ]

        if os.path.isdir(wid.item_dir):
            context_menu.add_action(
                action=context_actions.open_thumb,
                callback=lambda: self.view_folder_cmd(wid.item_dir)
            )
            context_menu.add_action(
                action=context_actions.new_main_win,
                callback=lambda: self.base_signals.new_main_win.emit(wid.item_dir)
            )
            if wid.item_dir in JsonData.favs:
                context_menu.add_action(
                    action=context_actions.fav_remove,
                    callback=lambda: self.fav_cmd(offset=-1, src=wid.item_dir)
                )
            else:
                context_menu.add_action(
                    action=context_actions.fav_add,
                    callback=lambda: self.fav_cmd(offset=1, src=wid.item_dir)
                )
        else:
            context_menu.add_action(
                action=context_actions.open_thumb,
                callback=lambda: self.view_image_cmd(wid.item_dir)
            )
        context_menu.addSeparator()
        context_menu.add_action(
            action=context_actions.win_info,
            callback=lambda: self.base_signals.info.emit(urls)
        )
        context_menu.add_action(
            action=context_actions.reveal,
            callback=lambda: self.base_signals.reveal_urls.emit(urls)
        )
        context_menu.add_action(
            context_actions.copy_path,
            callback=lambda: self.base_signals.copy_urls.emit(urls)
        )
        context_menu.add_action(
            context_actions.copy_name,
            callback=lambda: self.base_signals.copy_names.emit(urls)
        )
        context_menu.show_under_mouse()
        wid.default_style()

    def mouseReleaseEvent(self, a0):
        wid: PathItem = self.childAt(a0.pos())
        if not isinstance(wid, (PathItem, QLabel)):
            return
        if isinstance(wid, QLabel):
            wid: PathItem = wid.parent()
        if a0.button() == Qt.MouseButton.LeftButton:
            if wid.item_dir == self.main_win_item.abs_current_dir:
                return
            if os.path.isdir(wid.item_dir):
                self.base_signals.history_item.emit(wid.item_dir)
                self.base_signals.load_st_grid.emit(wid.item_dir)
            else:
                self.view_image_cmd(wid.item_dir)
        return super().mouseReleaseEvent(a0)
    