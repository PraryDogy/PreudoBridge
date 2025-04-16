import os

from PyQt5.QtCore import QMimeData, QPoint, Qt, QTimer, QUrl, pyqtSignal
from PyQt5.QtGui import QContextMenuEvent, QDrag, QMouseEvent, QPixmap
from PyQt5.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel,
                             QVBoxLayout, QWidget)

from cfg import Dynamic, Static
from database import ORDER_DICT
from utils import Utils

from ._base_widgets import UFrame, UMenu, USvgSqareWidget
from .actions import CopyPath, Info, RevealInFinder, SortMenu, View
from .info_win import InfoWin

SORT_T = "Сортировка"
TOTAL_T = "Всего"
ASC = "по убыв."
DESC = "по возр."
GO_T = "Перейти"
CURR_WID = "curr_wid"
FINDER_T = "Finder"
GO_PLACEGOLDER = "Вставьте путь к файлу/папке"
ARROW_RIGHT = " \U0000203A" # ›


class PathItem(QWidget):
    min_wid = 5
    new_history_item = pyqtSignal(str)
    load_st_grid_sig = pyqtSignal(tuple)
    open_img_view = pyqtSignal(str)

    def __init__(self, src: str, name: str):
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
        self.setFixedHeight(15)
        self.src = src

        item_layout = QHBoxLayout()
        item_layout.setContentsMargins(0, 0, 0, 0)
        item_layout.setSpacing(5)
        self.setLayout(item_layout)

        self.img_wid = USvgSqareWidget(size=15)
        item_layout.addWidget(self.img_wid)
        
        self.text_wid = QLabel(text=name)
        self.collapse()
        item_layout.addWidget(self.text_wid)

    def add_arrow(self):
        """
        Добавляет к тексту виджета ">"
        """
        t = self.text_wid.text() + " " + ARROW_RIGHT
        self.text_wid.setText(t)

    def expand(self):
        """
        Показывает виджет в полную длину
        """
        self.text_wid.setFixedWidth(self.text_wid.sizeHint().width())
 
    def view_(self, *args):
        """
        При двойном клике на виджет или вызове контестного
        меню пункта "Просмотр"  
        Для файлов будет открыт просмотрщик     
        Для папок будет загружена новая сетка с указанной директорией
        """
        if os.path.isfile(self.src):
            self.open_img_view.emit(self.src)
        else:
            self.new_history_item.emit(self.src)
            self.load_st_grid_sig.emit((self.src, None))

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

    def win_info_cmd(self):
        """
        Открывает меню информации о файле / папке
        """
        self.win_info = InfoWin(self.src)
        self.win_info.center(self.window())
        self.win_info.show()

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

    def mouseReleaseEvent(self, a0):
        """
        Открывает просмотрщик для файлов или загружает новую сетку для папок
        по левому клику мыши
        """
        if a0.button() == Qt.MouseButton.LeftButton:
            self.view_()

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

        self.drag.setPixmap(QPixmap(Static.COPY_FILES_PNG))
        
        url = [QUrl.fromLocalFile(self.src)]
        self.mime_data.setUrls(url)

        self.drag.setMimeData(self.mime_data)
        self.drag.exec_(Qt.DropAction.CopyAction)
        self.default_style()

    def contextMenuEvent(self, ev: QContextMenuEvent | None) -> None:
        menu = UMenu(parent=self)

        view_action = View(menu)
        view_action.triggered.connect(self.view_)
        menu.addAction(view_action)

        menu.addSeparator()

        info = Info(menu)
        info.triggered.connect(self.win_info_cmd)
        menu.addAction(info)

        show_in_finder_action = RevealInFinder(menu, self.src)
        menu.addAction(show_in_finder_action)

        copy_path = CopyPath(menu, self.src)
        menu.addAction(copy_path)

        self.solid_style()
        menu.show_()
        self.default_style()


class PathBar(QWidget):
    new_history_item = pyqtSignal(str)
    load_st_grid_sig = pyqtSignal(tuple)
    resize_grid_sig = pyqtSignal()
    open_img_view = pyqtSignal(str)

    def __init__(self):
        """
        Нижний бар:     
        - Группа виджетов PathItem (читай описание PathItem)  
        """
        super().__init__()
        self.setFixedHeight(20)
        self.setAcceptDrops(True)
        self.current_path: str = None

        self.main_lay = QHBoxLayout()
        self.main_lay.setContentsMargins(0, 0, 0, 0)
        self.main_lay.setSpacing(5)
        self.main_lay.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.setLayout(self.main_lay)

        # self.path_wid = QWidget()
        # self.main_lay.insertWidget(0, self.path_wid, alignment=Qt.AlignmentFlag.AlignLeft)

        # self.path_lay = QHBoxLayout()
        # self.path_lay.setContentsMargins(0, 0, 0, 0)
        # self.path_lay.setSpacing(5)
        # self.path_wid.setLayout(self.path_lay)

        # 2 строка сепаратор
        # sep = QFrame()
        # sep.setStyleSheet("background: rgba(0, 0, 0, 0.2)")
        # sep.setFixedHeight(1)
        # self.main_lay.addWidget(sep)

    def path_bar_update_cmd(self, dir: str):
        print(dir)
        """  
        Путь сетки / папки / файла
        Можно передать None
        Если выделить виджет в сетке, нижний бар отобразит путь к виджету   
        Если ничего не выделено, то отображается текущая директория сетки   
        """
        if dir:
            self.set_new_path(dir)

    def set_new_path(self, dir: str):
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
        limit = 40

        for x, name in enumerate(root, start=1):
            dir = os.path.join(os.sep, *root[:x])
            path_item = PathItem(dir, name)
            cmd_ = lambda dir: self.new_history_item.emit(dir)
            path_item.new_history_item.connect(cmd_)
            path_item.load_st_grid_sig.connect(self.load_st_grid_sig.emit)
            path_item.open_img_view.connect(self.open_img_view.emit)

            if x == 1:
                icon = Static.COMP_SVG
                path_item.add_arrow()

            elif x == 2:
                icon = Static.HDD_SVG
                path_item.add_arrow()

            elif x == len(root):
                if os.path.isdir(dir):
                    icon = Static.FOLDER_SVG
                else:
                    _, ext = os.path.splitext(dir)
                    icon = Utils.get_generic_icon_path(ext)

                if len(name) > limit:
                    path_item.text_wid.setText(name[:limit] + "...")

                # последний элемент показывать в полный размер
                path_item.expand()
                # отключаем функции схлопывания и развертывания
                path_item.enterEvent = lambda *args, **kwargs: None
                path_item.leaveEvent = lambda *args, **kwargs: None

            else:
                icon = Static.FOLDER_SVG
                path_item.add_arrow()

            path_item.img_wid.load(icon)
            self.main_lay.addWidget(path_item)
