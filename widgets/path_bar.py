import os

from PyQt5.QtCore import QMimeData, Qt, QTimer, QUrl, pyqtSignal
from PyQt5.QtGui import QContextMenuEvent, QDrag, QMouseEvent, QPixmap
from PyQt5.QtWidgets import QApplication, QHBoxLayout, QLabel, QWidget

from cfg import JsonData, Static
from system.items import BaseItem, MainWinItem
from system.utils import Utils

from ._base_widgets import UMenu, USvgSqareWidget
from .actions import ItemActions


class PathItem(QWidget):
    min_wid = 5
    new_history_item = pyqtSignal(str)
    load_st_grid = pyqtSignal()
    arrow_right = " \U0000203A" # ›
    height_ = 15
    info_win = pyqtSignal(list)
    add_fav = pyqtSignal(str)
    del_fav = pyqtSignal(str)

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
        self.setFixedHeight(PathItem.height_)
        self.dir = dir

        item_layout = QHBoxLayout()
        item_layout.setContentsMargins(0, 0, 0, 0)
        item_layout.setSpacing(5)
        self.setLayout(item_layout)

        self.img_wid = USvgSqareWidget(None, PathItem.height_)
        item_layout.addWidget(self.img_wid)
        
        self.text_wid = QLabel(text=name)
        self.collapse()
        item_layout.addWidget(self.text_wid)

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
                background: {Static.BLUE_GLOBAL};
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

    def open_info_win(self):
        """
        Открыть окно информации о файле / папке
        """
        base_item = BaseItem(self.dir)
        base_item.set_properties()
        self.info_win.emit([base_item, ])

    def fav_cmd(self, offset: int, src: str):
        (self.add_fav if offset == 1 else self.del_fav).emit(src)

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

    def contextMenuEvent(self, ev: QContextMenuEvent | None) -> None:
        urls = [self.main_win_item.main_dir]
        names = [os.path.basename(i) for i in urls]
        total = len(urls)

        menu_ = UMenu(parent=self)

        if self.dir in JsonData.favs:
            cmd_ = lambda: self.fav_cmd(offset=-1, src=self.dir)
            fav_action = ItemActions.FavRemove(menu_)
            fav_action.triggered.connect(cmd_)
            menu_.addAction(fav_action)
        else:
            cmd_ = lambda: self.fav_cmd(offset=1, src=self.dir)
            fav_action = ItemActions.FavAdd(menu_)
            fav_action.triggered.connect(cmd_)
            menu_.addAction(fav_action)

        info = ItemActions.Info(menu_)
        info.triggered.connect(self.open_info_win)
        menu_.addAction(info)

        menu_.addSeparator()

        show_in_finder_action = ItemActions.RevealInFinder(menu_, urls)
        menu_.addAction(show_in_finder_action)

        copy_path = ItemActions.CopyPath(menu_, urls)
        menu_.addAction(copy_path)

        copy_name = ItemActions.CopyName(menu_, names)
        menu_.addAction(copy_name)

        self.solid_style()
        menu_.show_under_cursor()
        self.default_style()

    def mouseReleaseEvent(self, a0):
        if a0.button() == Qt.MouseButton.LeftButton:
            if os.path.isdir(self.dir) and self.dir != self.main_win_item.main_dir:
                self.main_win_item.main_dir = self.dir
                self.new_history_item.emit(self.dir)
                self.load_st_grid.emit()
        return super().mouseReleaseEvent(a0)


class PathBar(QWidget):
    new_history_item = pyqtSignal(str)
    load_st_grid = pyqtSignal()
    info_win = pyqtSignal(list)
    add_fav = pyqtSignal(str)
    del_fav = pyqtSignal(str)
    last_item_limit = 40
    height_ = 25

    def __init__(self, main_win_item: MainWinItem):
        """
        Нижний бар:     
        - Группа виджетов PathItem (читай описание PathItem)  
        """
        super().__init__()
        self.main_win_item = main_win_item
        self.setFixedHeight(PathBar.height_)
        self.setAcceptDrops(True)
        self.current_path: str = None

        self.main_lay = QHBoxLayout()
        self.main_lay.setContentsMargins(0, 0, 0, 0)
        self.main_lay.setSpacing(5)
        self.main_lay.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.setLayout(self.main_lay)

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
            cmd_ = lambda dir: self.new_history_item.emit(dir)
            path_item.new_history_item.connect(cmd_)
            path_item.load_st_grid.connect(self.load_st_grid.emit)
            path_item.info_win.connect(lambda lst: self.info_win.emit(lst))
            path_item.add_fav.connect(self.add_fav.emit)
            path_item.del_fav.connect(self.del_fav.emit)
            path_item.img_wid.load(Static.app_icons_dir.get("folder.svg"))
            path_item.add_arrow()
            path_items[x] = path_item
            self.main_lay.addWidget(path_item)

        path_items.get(1).img_wid.load(Static.app_icons_dir.get("computer.svg"))

        if path_items.get(2):
            path_items.get(2).img_wid.load(Static.app_icons_dir.get("hdd.svg"))

        last_item = path_items.get(len(root))

        if last_item:
            
            if len(root) > 2:
                if not os.path.exists(last_item.dir):
                    icon = Static.app_icons_dir.get("question.svg")
                elif os.path.isdir(last_item.dir):
                    icon = Static.app_icons_dir.get("folder.svg")
                else:
                    _, ext = os.path.splitext(last_item.dir)
                    icon = Utils.get_icon_path(ext, Static.ext_icons_dir)
                last_item.img_wid.load(icon)

            text_ = last_item.text_wid.text()
            if len(text_) > PathBar.last_item_limit:
                path_item.text_wid.setText(text_[:PathBar.last_item_limit] + "...")

            last_item.del_arrow()
            last_item.expand()
            last_item.enterEvent = lambda *args, **kwargs: None
            last_item.leaveEvent = lambda *args, **kwargs: None

