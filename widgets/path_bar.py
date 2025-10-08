import os

from PyQt5.QtCore import QMimeData, Qt, QTimer, QUrl, pyqtSignal
from PyQt5.QtGui import QContextMenuEvent, QDrag, QMouseEvent, QPixmap
from PyQt5.QtWidgets import QApplication, QHBoxLayout, QLabel, QWidget

from cfg import Static
from system.items import BaseItem, MainWinItem
from system.utils import Utils

from ._base_widgets import UMenu, USvgSqareWidget
from .actions import ItemActions


class PathItem(QWidget):
    min_wid = 5
    new_history_item = pyqtSignal(str)
    load_st_grid = pyqtSignal()
    open_img_view = pyqtSignal(str)
    open_in_new_win = pyqtSignal(str)
    arrow_right = " \U0000203A" # ›
    height_ = 15
    info_win = pyqtSignal(list)

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
 
    def open_single_cmd(self, *args):
        self.open_img_view.emit(self.dir)

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

    def mouseDoubleClickEvent(self, a0):
        self.open_img_view.emit(self.dir)
        return super().mouseDoubleClickEvent(a0)

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

    def mousePressEvent(self, a0: QMouseEvent | None) -> None:
        """
        Начать перемещение виджета
        """
        if a0.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = a0.pos()

    def mouseMoveEvent(self, a0: QMouseEvent | None) -> None:
        """
        Можно перетащить виджет:        
        На меню избранного в приложении, в случае если это директория,
        будет добавлено новое избранное     
        На сетку - ничего не будет      
        Вне приложения, будет скопирована папка / файл в место назначения
        """
        if a0.button() == Qt.MouseButton.RightButton:
            return
        
        try:
            distance = (a0.pos() - self.drag_start_position).manhattanLength()
        except AttributeError:
            return

        if distance < QApplication.startDragDistance():
            return

        self.solid_style()
        self.drag = QDrag(self)
        self.mime_data = QMimeData()

        self.drag.setPixmap(QPixmap(Static.INTERNAL_ICONS.get("files.svg")))
        
        url = [QUrl.fromLocalFile(self.dir)]
        self.mime_data.setUrls(url)

        self.drag.setMimeData(self.mime_data)
        self.drag.exec_(Qt.DropAction.CopyAction)
        self.default_style()

    def contextMenuEvent(self, ev: QContextMenuEvent | None) -> None:
        urls = [self.main_win_item.main_dir]
        names = [os.path.basename(i) for i in urls]
        total = len(urls)

        menu = UMenu(parent=self)

        open_single = ItemActions.OpenSingle(menu)
        open_single.triggered.connect(self.open_single_cmd)
        menu.addAction(open_single)

        if os.path.isdir(self.dir):
            new_win = ItemActions.OpenInNewWindow(menu)
            new_win.triggered.connect(lambda: self.open_in_new_win.emit(self.dir))
            menu.addAction(new_win)

        info = ItemActions.Info(menu)
        info.triggered.connect(self.open_info_win)
        menu.addAction(info)

        menu.addSeparator()

        show_in_finder_action = ItemActions.RevealInFinder(menu, urls)
        menu.addAction(show_in_finder_action)

        copy_path = ItemActions.CopyPath(menu, urls)
        menu.addAction(copy_path)

        copy_name = ItemActions.CopyName(menu, names)
        menu.addAction(copy_name)

        self.solid_style()
        menu.show_under_cursor()
        self.default_style()


class PathBar(QWidget):
    new_history_item = pyqtSignal(str)
    load_st_grid = pyqtSignal()
    img_view_win = pyqtSignal(str)
    open_in_new_win = pyqtSignal(str)
    info_win = pyqtSignal(list)
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
            path_item.open_img_view.connect(lambda dir: self.img_view_win.emit(dir))
            path_item.open_in_new_win.connect(lambda dir: self.open_in_new_win.emit(dir))
            path_item.info_win.connect(lambda lst: self.info_win.emit(lst))
            path_item.img_wid.load(Static.INTERNAL_ICONS.get("folder.svg"))
            path_item.add_arrow()
            path_items[x] = path_item
            self.main_lay.addWidget(path_item)

        path_items.get(1).img_wid.load(Static.INTERNAL_ICONS.get("computer.svg"))

        if path_items.get(2):
            path_items.get(2).img_wid.load(Static.INTERNAL_ICONS.get("hdd.svg"))

        last_item = path_items.get(len(root))

        if last_item:
            
            if len(root) > 2:
                if not os.path.exists(last_item.dir):
                    icon = Static.INTERNAL_ICONS.get("question.svg")
                elif os.path.isdir(last_item.dir):
                    icon = Static.INTERNAL_ICONS.get("folder.svg")
                else:
                    _, ext = os.path.splitext(last_item.dir)
                    icon = Utils.get_icon_path(ext, Static.EXTERNAL_ICONS)
                last_item.img_wid.load(icon)

            text_ = last_item.text_wid.text()
            if len(text_) > PathBar.last_item_limit:
                path_item.text_wid.setText(text_[:PathBar.last_item_limit] + "...")

            last_item.del_arrow()
            last_item.expand()
            last_item.enterEvent = lambda *args, **kwargs: None
            last_item.leaveEvent = lambda *args, **kwargs: None

