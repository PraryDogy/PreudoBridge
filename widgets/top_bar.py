import subprocess

from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.QtWidgets import (QFrame, QGridLayout, QLabel, QLineEdit, QMenu,
                             QPushButton, QSizePolicy, QSpacerItem,
                             QVBoxLayout, QWidget)

from cfg import Config
from path_finder import PathFinderThread


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
    level_up_btn_press = pyqtSignal()
    open_path_btn_press = pyqtSignal(str)

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

        self.level_up_button = QPushButton(text="↑", parent=self)
        self.level_up_button.setToolTip(" Перейти на уровень выше ")
        self.level_up_button.setFixedWidth(60)
        self.level_up_button.clicked.connect(self.level_up_btn_press.emit)
        self.grid_layout.addWidget(self.level_up_button, 0, 1)

        self.open_btn = QPushButton("Открыть путь")
        self.open_btn.clicked.connect(self.open_path_btn_cmd)
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
    
    def open_path_btn_cmd(self):
        path = self.paste_text()
        self.path_thread = PathFinderThread(path)
        self.path_thread.finished.connect(
            lambda res: self.open_path_btn_press.emit(res)
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
