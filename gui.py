import json
import os
import subprocess

from PyQt5.QtCore import QDir, QEvent, QObject, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QKeyEvent, QResizeEvent
from PyQt5.QtWidgets import (QAction, QApplication, QFileSystemModel, QFrame,
                             QGridLayout, QLabel, QLineEdit, QMenu,
                             QPushButton, QSizePolicy, QSpacerItem, QSplitter,
                             QTabBar, QTabWidget, QTreeView, QVBoxLayout,
                             QWidget)

from cfg import Config
from path_finder import PathFinderThread
from utils import Utils
from widgets.grid_standart import (GridStandart, GridStandartThreads,
                                       LoadImagesThread)


class SortTypeWidget(QPushButton):
    sort_click = pyqtSignal()

    def __init__(self, parent: QWidget):
        super().__init__()
        self.setFixedWidth(110)
        self.setToolTip(" Сортировка файлов ")

        self.data = {
                "name": "Имя",
                "size": "Размер",
                "modify": "Дата изм.",
                "type": "Тип",
                }

        text = self.data[Config.json_data["sort"]]
        self.setText(text)

        menu = QMenu()
        self.setMenu(menu)

        for k, v in self.data.items():
            action = menu.addAction(v)
            action.triggered.connect(lambda e, k=k: self.action_clicked(k))

    def action_clicked(self, text: str):
        Config.json_data["sort"] = text
        self.setText(self.data[text])
        self.sort_click.emit()


class SearchWidget(QWidget):
    search_text_sig = pyqtSignal(str)
    search_clear_sig = pyqtSignal()

    def __init__(self):
        super().__init__()

        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(0, 0, 0, 0)
        v_lay.setSpacing(0)
        self.setLayout(v_lay)

        input_wid = QLineEdit()
        input_wid.setPlaceholderText("Поиск")
        input_wid.setStyleSheet("padding-left: 2px;")
        input_wid.setFixedSize(200, 25)
        v_lay.addWidget(input_wid)

        self.clear_btn = QLabel(parent=self, text="x")
        self.clear_btn.setFixedSize(10, 10)
        self.clear_btn.move(180, 7)
        self.clear_btn.hide()
        self.clear_btn.mouseReleaseEvent = lambda e: input_wid.clear()

        input_wid.textChanged.connect(self.on_text_changed)
        self.search_text: str = None

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(
            lambda: self.search_text_sig.emit(self.search_text)
            )

    def on_text_changed(self, text):
        if text:
            self.clear_btn.show()
            self.search_text = text
            self.search_timer.stop()
            self.search_timer.start(1000)
        else:
            self.clear_btn.hide()
            self.search_clear_sig.emit()


class TopBarWidget(QFrame):
    sort_btn_press = pyqtSignal()
    up_btn_press = pyqtSignal()
    open_btn_press = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.root: str = None
        self.path_labels_list: list = []
        self.setFixedHeight(40)
        self.init_ui()

    def init_ui(self):
        self.grid_layout = QGridLayout()
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.grid_layout)

        l_spacer = QSpacerItem(1, 1, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.grid_layout.addItem(l_spacer, 0, 0)

        self.up_button = QPushButton(text="↑", parent=self)
        self.up_button.setToolTip(" Перейти на уровень выше ")
        self.up_button.setFixedWidth(60)
        self.up_button.clicked.connect(self.up_btn_press.emit)
        self.grid_layout.addWidget(self.up_button, 0, 1)

        self.open_btn = QPushButton("Открыть путь")
        self.open_btn.clicked.connect(self.open_btn_cmd)
        self.grid_layout.addWidget(self.open_btn, 0, 2)

        self.sort_widget = SortTypeWidget(parent=self)
        self.sort_widget.sort_click.connect(self.sort_btn_press.emit)
        self.grid_layout.addWidget(self.sort_widget, 0, 3)

        self.ubiv = "↓↑"
        self.vozrast = "↑↓"
        sort_t = self.ubiv if Config.json_data["reversed"] else self.vozrast
        self.sort_button = QPushButton(text=sort_t, parent=self)
        self.sort_button.setToolTip(" Сортировка файлов: по возрастанию / по убыванию ")
        self.sort_button.setFixedWidth(60)
        self.sort_button.clicked.connect(self.on_sort_toggle)
        self.grid_layout.addWidget(self.sort_button, 0, 4)

        r_spacer = QSpacerItem(1, 1, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.grid_layout.addItem(r_spacer, 0, 5)

        self.search_box = SearchWidget()
        self.grid_layout.addWidget(self.search_box, 0, 6)

        last_spacer = QSpacerItem(10, 1)
        self.grid_layout.addItem(last_spacer, 0, 7)

    def paste_text(self) -> str:
        paste_result = subprocess.run(
            ['pbpaste'],
            capture_output=True,
            text=True,
            check=True
            )
        return paste_result.stdout.strip()
    
    def open_btn_cmd(self):
        path = self.paste_text()
        self.path_thread = PathFinderThread(path)
        self.path_thread.finished.connect(
            lambda res: self.open_btn_press.emit(res)
            )
        
        self.path_thread.start()

    def on_sort_toggle(self):
        if Config.json_data["reversed"]:
            Config.json_data["reversed"] = False
            self.sort_button.setText(self.vozrast)
        else:
            Config.json_data["reversed"] = True
            self.sort_button.setText(self.ubiv)
        self.sort_btn_press.emit()


class TreeWidget(QTreeView):
    on_tree_clicked = pyqtSignal(str)

    def __init__(self):
        super().__init__()

        self.model = QFileSystemModel()
        self.model.setFilter(QDir.AllDirs | QDir.NoDotAndDotDot)
        self.model.setRootPath("/Volumes")
        self.setModel(self.model)
        self.setRootIndex(self.model.index("/Volumes"))

        self.setHeaderHidden(True)
        for i in range(1, self.model.columnCount()):
            self.setColumnHidden(i, True)

        self.setIndentation(10)
        self.setUniformRowHeights(True)

        self.clicked.connect(self.one_clicked)

    def one_clicked(self, index):
        path = self.model.filePath(index)
        self.setCurrentIndex(index)
        self.on_tree_clicked.emit(path)

        if self.isExpanded(index):
            self.collapse(index)
        else:
            self.expand(index)

    def expand_path(self, root: str):
        index = self.model.index(root)
        self.setCurrentIndex(index)
        self.expand(index)

    def contextMenuEvent(self, event):
        index = self.indexAt(event.pos())
        if not index.isValid():
            return

        menu = QMenu(self)
        file_path = self.model.filePath(index)
        index = self.model.index(file_path)

        open_finder_action = QAction("Просмотр", self)
        open_finder_action.triggered.connect(lambda: self.one_clicked(index))
        menu.addAction(open_finder_action)

        menu.addSeparator()

        open_finder_action = QAction("Показать в Finder", self)
        open_finder_action.triggered.connect(lambda: self.open_in_finder(file_path))
        menu.addAction(open_finder_action)

        copy_path_action = QAction("Скопировать путь до папки", self)
        copy_path_action.triggered.connect(lambda: Utils.copy_path(file_path))
        menu.addAction(copy_path_action)

        menu.exec_(self.mapToGlobal(event.pos()))

    def open_in_finder(self, path: str):
        subprocess.call(["open", "-R", path])


class SimpleFileExplorer(QWidget):
    def __init__(self):
        super().__init__()

        self.clmn_count = 1
        self.finder_items = []
        self.finder_images: dict = {}
        self.grid: QGridLayout = None

        ww, hh = Config.json_data["ww"], Config.json_data["hh"]
        self.resize(ww, hh)
        self.move_to_filepath: str = None

        main_lay = QVBoxLayout()
        main_lay.setContentsMargins(5, 5, 5, 5)
        main_lay.setSpacing(0)
        self.setLayout(main_lay)

        splitter_wid = QSplitter(Qt.Horizontal)
        splitter_wid.splitterMoved.connect(self.resizeEvent)
        main_lay.addWidget(splitter_wid)

        self.left_wid = QTabWidget()
        splitter_wid.addWidget(self.left_wid)
        splitter_wid.setStretchFactor(0, 0)
        
        self.tree_wid = TreeWidget()
        self.tree_wid.on_tree_clicked.connect(self.on_tree_clicked)
        self.left_wid.addTab(self.tree_wid, "Файлы")
        self.left_wid.addTab(QLabel("Тут будут каталоги"), "Сохраненные")

        right_wid = QWidget()
        splitter_wid.addWidget(right_wid)
        splitter_wid.setStretchFactor(1, 1)

        self.r_lay = QVBoxLayout()
        self.r_lay.setContentsMargins(0, 0, 0, 0)
        self.r_lay.setSpacing(0)
        right_wid.setLayout(self.r_lay)
        
        self.top_bar = TopBarWidget()
        self.top_bar.sort_btn_press.connect(self.load_standart_grid)
        self.top_bar.up_btn_press.connect(self.btn_up_cmd)
        self.top_bar.open_btn_press.connect(self.open_custom_path)
        self.r_lay.addWidget(self.top_bar)



        self.resize_timer = QTimer(parent=self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.setInterval(500)
        self.resize_timer.timeout.connect(self.load_standart_grid)

        self.first_load()
        self.setWindowTitle(Config.json_data["root"])

    def on_tree_clicked(self, root: str):
        Config.json_data["root"] = root
        self.setWindowTitle(root)
        self.load_standart_grid()

    def open_custom_path(self, path: str):
        if not os.path.exists(path):
            return

        if os.path.isfile(path):
            if path.endswith(Config.img_ext):
                self.move_to_filepath = path
            path, _ = os.path.split(path)

        Config.json_data["root"] = path
        self.tree_wid.expand_path(path)
        self.setWindowTitle(path)
        self.load_standart_grid()

    def btn_up_cmd(self):
        path = os.path.dirname(Config.json_data["root"])
        Config.json_data["root"] = path

        self.tree_wid.expand_path(path)
        self.setWindowTitle(Config.json_data["root"])
        self.load_standart_grid()

    def load_standart_grid(self):
        if self.grid:
            self.grid.deleteLater()

        ww = self.get_grid_width()
        self.grid = GridStandart(width=ww, root=Config.json_data["root"])
        self.r_lay.addWidget(self.grid)

    def first_load(self):
        root = Config.json_data["root"]

        if root and os.path.exists(root):
            self.tree_wid.expand_path(root)
            self.load_standart_grid()

    def resizeEvent(self, a0: QResizeEvent | None) -> None:
        Config.json_data["ww"] = self.geometry().width()
        Config.json_data["hh"] = self.geometry().height()
        self.resize_timer.stop()
        self.resize_timer.start()
        # return super().resizeEvent(a0)

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        self.hide()
        a0.ignore()

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() == Qt.Key.Key_Up:
            if a0.modifiers() == Qt.KeyboardModifier.MetaModifier:
                self.btn_up_cmd()

        elif a0.key() == Qt.Key.Key_W:
            if a0.modifiers() == Qt.KeyboardModifier.ControlModifier:
                self.hide()

        elif a0.key() == Qt.Key.Key_Q:
            if a0.modifiers() == Qt.KeyboardModifier.ControlModifier:
                QApplication.instance().quit()

    def get_grid_width(self):
        return Config.json_data["ww"] - self.left_wid.width() - 180


class CustomApp(QApplication):
    def __init__(self, argv: list[str]) -> None:
        super().__init__(argv)
        self.aboutToQuit.connect(self.on_exit)
        self.installEventFilter(self)

    def eventFilter(self, a0: QObject | None, a1: QEvent | None) -> bool:
        if a1.type() == QEvent.Type.ApplicationActivate:
            Utils.get_main_win().show()

        return False

    def on_exit(self):
        with open(Config.json_file, 'w') as f:
            json.dump(Config.json_data, f, indent=4, ensure_ascii=False)
