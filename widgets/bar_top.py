import os
from difflib import SequenceMatcher

import sqlalchemy
from PyQt5.QtCore import QSize, Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QKeyEvent, QMouseEvent, QCursor
from PyQt5.QtWidgets import (QAction, QFrame, QGridLayout, QHBoxLayout, QLabel,
                             QLineEdit, QMenu, QPushButton, QSlider,
                             QSpacerItem, QTabBar, QVBoxLayout, QWidget)

from cfg import Config
from database import CACHE, STATS, Dbase, Engine
from utils import Utils


class PathFinderThread(QThread):
    _finished = pyqtSignal(str)

    def __init__(self, src: str):
        super().__init__()
        self.src: str = src
        self.result: str = None
        self.volumes: list[str] = []
        self.exclude = "/Volumes/Macintosh HD/Volumes/"

    def run(self):
        self._path_finder()
        if not self.result:
            self._finished.emit("")
        elif self.result in self.volumes:
            self._finished.emit("")
        elif self.result:
            self._finished.emit(self.result)

    def _path_finder(self):
        src = os.sep + self.src.replace("\\", os.sep).strip().strip(os.sep)
        src_splited = [i for i in src.split(os.sep) if i]

        self.volumes = [
            os.path.join("/Volumes", i)
            for i in os.listdir("/Volumes")
            ]

        volumes_extra = [
            os.path.join(vol, *extra.strip().split(os.sep))
            for extra in Config.json_data.get("extra_paths")
            for vol in self.volumes
            ]
        
        self.volumes.extend(volumes_extra)

        # обрезаем входящий путь каждый раз на 1 секцию с конца
        cut_paths: list = [
                os.path.join(*src_splited[:i])
                for i in range(len(src_splited) + 1)
                if src_splited[:i]
                ]

        # обрезаем каждый путь на 1 секцию с начала и прибавляем элементы из volumes
        all_posible_paths: list = []

        for p_path in sorted(cut_paths, key=len, reverse=True):
            p_path_split = [i for i in p_path.split(os.sep) if i]
            
            for share in self.volumes:
                for i in range(len(p_path_split) + 1):

                    all_posible_paths.append(
                        os.path.join(share, *p_path_split[i:])
                        )

        # из всех полученных возможных путей ищем самый подходящий существующий путь
        for i in sorted(all_posible_paths, key=len, reverse=True):
            if self.exclude in i:
                print("ignore strange folder", self.exclude)
                continue
            if os.path.exists(i):
                self.result = i
                break

        # смотрим совпадает ли последняя секция входящего и полученного пути
        tail = []

        if self.result:
            result_tail = self.result.split(os.sep)[-1]
            if src_splited[-1] != result_tail:
                try:
                    tail = src_splited[src_splited.index(result_tail) + 1:]
                except ValueError:
                    return

        # пытаемся найти секции пути, написанные с ошибкой
        for a in tail:
            dirs = [x for x in os.listdir(self.result)]

            for b in dirs:
                matcher = SequenceMatcher(None, a, b).ratio()
                if matcher >= 0.85:
                    self.result = os.path.join(self.result, b)
                    break


class ActionData:
    def __init__(self, sort: str | None, reversed: bool, text: str):
        self.sort: str | None = sort
        self.reversed: bool = reversed
        self.text: str = text


class SortTypeBtn(QPushButton):
    sort_click = pyqtSignal()

    def __init__(self, parent: QWidget):
        super().__init__()
        self.setFixedWidth(125)
        self.setStyleSheet("text-align: center;")
                
        data_actions = (
            ActionData(None, False, "По возрастанию"),
            ActionData("name", False, "Имя возр"),
            ActionData("size", False, "Размер возр"),
            ActionData("modify", False, "Дата возр"),
            ActionData("type", False, "Тип возр"),
            ActionData("colors", False, "Цвета возр"),

            ActionData(None, True, "По убыванию"),
            ActionData("name", True, "Имя убыв"),
            ActionData("size", True, "Размер убыв"),
            ActionData("modify", True, "Дата убыв"),
            ActionData("type", True, "Тип убыв"),
            ActionData("colors", True, "Цвета убыв"),
            )

        menu = QMenu()
        self.setMenu(menu)

        for data_action in data_actions:
            action = QAction(parent=self, text=data_action.text)
            action.triggered.connect(lambda e, d=data_action: self._action_clicked(d))

            if data_action.sort == None:
                action.setDisabled(True)

            if data_action.sort == Config.json_data.get("sort"):
                if data_action.reversed == Config.json_data.get("reversed"):
                    self.setText(data_action.text)

            menu.addAction(action)

    def _action_clicked(self, data_action: ActionData):
        Config.json_data["sort"] = data_action.sort
        Config.json_data["reversed"] = data_action.reversed
        self.setText(data_action.text)
        self.sort_click.emit()


class ViewTypeBtn(QTabBar):
    view_click = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setFixedWidth(125)

        self.addTab("Плитка")
        self.addTab("Список")

        if Config.json_data.get("list_view"):
            self.setCurrentIndex(1)
        else:
            self.setCurrentIndex(0)

        self.tabBarClicked.connect(self.set_view_cmd)

    def set_view_cmd(self, index: int):
        if index == 0:
            self.setCurrentIndex(0)
            Config.json_data["list_view"] = False
        else:
            self.setCurrentIndex(1)
            Config.json_data["list_view"] = True
        self.view_click.emit()

    def tabSizeHint(self, index):
        size = QTabBar.tabSizeHint(self, index)
        return QSize(10, size.height())


class SearchWidget(QWidget):
    start_search_sig = pyqtSignal(str)
    stop_search_sig = pyqtSignal()
    clear_search_sig = pyqtSignal()

    def __init__(self):
        super().__init__()

        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(0, 0, 0, 0)
        v_lay.setSpacing(0)
        self.setLayout(v_lay)

        self.input_wid = QLineEdit()
        self.input_wid.setPlaceholderText("Поиск")
        self.input_wid.setStyleSheet("padding-left: 2px; padding-right: 20px;")
        self.input_wid.setFixedSize(170, 25)
        self.input_wid.mouseDoubleClickEvent = self._show_templates
        v_lay.addWidget(self.input_wid)

        self.clear_btn = QLabel(parent=self, text="\u2573")
        self.clear_btn.setFixedSize(15, 10)
        self.clear_btn.move(self.input_wid.width() - 20, 8)
        self.clear_btn.hide()
        self.clear_btn.mouseReleaseEvent = lambda e: self.input_wid.clear()

        self.input_wid.textChanged.connect(self._on_text_changed)
        self.search_text: str = None

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(
            lambda: self.start_search_sig.emit(self.search_text)
            )
        
        self.clear_search_sig.connect(self._costil)

        self.templates_menu = QMenu()

        data = {
            "Найти jpg": str((".jpg", ".jpeg", "jfif")),
            "Найти tiff": str((".tif", ".tiff")),
            "Найти psd/psb": str((".psd", ".psb")),
            "Найти raw": str((".nef", ".raw")),
            "Найти любые фото": str(Config.img_ext)
            }

        for k, v in data.items():
            action = QAction(parent=self, text=k)
            action.triggered.connect(lambda e, xx=v: self._action_cmd(xx))
            self.templates_menu.addAction(action)

    def _costil(self):
        self.input_wid.disconnect()
        self.input_wid.clear()
        self.clear_btn.hide()
        self.input_wid.textChanged.connect(self._on_text_changed)

    def _on_text_changed(self, text):
        self.search_timer.stop()
        if text:
            self.clear_btn.show()
            self.search_text = text
            self.search_timer.start(1000)
        else:
            self.clear_search_sig.emit()
            self.clear_btn.hide()
            self.stop_search_sig.emit()

    def _show_templates(self, a0: QMouseEvent | None) -> None:
        self.templates_menu.exec(self.mapToGlobal(self.rect().bottomLeft()))
    
    def _action_cmd(self, text: str):
        self.input_wid.setText(text)


class _FiltersBtn(QPushButton):
    def __init__(self):
        super().__init__(text="Фильтры")
        
        self._menu = QWidget()
        self._menu.setWindowFlags(Qt.Popup)
        self._menu.setLayout(QVBoxLayout())
        self._menu.layout().setContentsMargins(1, 1, 1, 1)
        self._menu.layout().setSpacing(1)
        self._menu.closeEvent = lambda e: self.press_check()

        self.color_data = {
            "🔴": {"text": "Красный", "bool": False},
            "🔵": {"text": "Синий", "bool": False},
            "🟠": {"text": "Оранжевый", "bool": False},
            "🟡": {"text": "Желтый", "bool": False},
            "🟢": {"text": "Зеленый", "bool": False},
            "🟣": {"text": "Фиолетовый", "bool": False},
            "🟤": {"text": "Коричневый", "bool": False}
            }
        
        self.counter = 0

        self.labels = {}
        for color, data in self.color_data.items():
            label = QLabel(color + " " + data.get("text"))
            label.setContentsMargins(15, 5, 15, 5)
            label.mousePressEvent = lambda e, w=label, c=color: self.toggle_label(w, c)
            self._menu.layout().addWidget(label)

    def mouseReleaseEvent(self, e):
        pont = self.rect().bottomLeft()
        self._menu.move(self.mapToGlobal(pont))
        self._menu.show()

    def toggle_label(self, widget: QLabel, color: str):
        key = self.color_data.get(color)
        if key.get("bool"):
            widget.setStyleSheet("")
            key["bool"] = False
            self.counter -= 1
        else:
            widget.setStyleSheet("background: #007AFF;")
            key["bool"] = True
            self.counter += 1
        
    def press_check(self):
        if self.counter == 0:
            self.setDown(False)
        else:
            self.setDown(True)


class WinGo(QWidget):
    open_path = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Перейти к ...")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlags(Qt.Window | Qt.CustomizeWindowHint | Qt.WindowCloseButtonHint)
        self.setFixedSize(290, 90)
        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(10, 10, 10, 10)
        v_lay.setSpacing(10)
        self.setLayout(v_lay)

        self.input_wid = QLineEdit()
        self.input_wid.setPlaceholderText("Вставьте путь к файлу/папке")
        self.input_wid.setStyleSheet("padding-left: 2px;")
        self.input_wid.setFixedSize(270, 25)
        v_lay.addWidget(self.input_wid, alignment=Qt.AlignmentFlag.AlignCenter)

        go_btn = QPushButton("Перейти")
        go_btn.setFixedWidth(130)
        go_btn.clicked.connect(self._open_path_btn_cmd)
        v_lay.addWidget(go_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def _open_path_btn_cmd(self):
        path: str = self.input_wid.text()

        if not path:
            return

        path: str = os.sep + path.strip().strip(os.sep)

        if os.path.exists(path):
            self.open_path.emit(path)
            self.close()
        else:
            self.path_thread = PathFinderThread(path)
            self.path_thread._finished.connect(self._finalize)
            self.path_thread.start()

    def _finalize(self, res: str):
        self.open_path.emit(res)
        self.close()

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() == Qt.Key.Key_Escape:
            self.close()
        return super().keyPressEvent(a0)
    

class WinSettings(QWidget):
    def __init__(self):
        super().__init__()
        
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlags(Qt.Window | Qt.CustomizeWindowHint | Qt.WindowCloseButtonHint)
        self.setWindowTitle("Настройки")
        self.setFixedSize(300, 150)

        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(10, 10, 10, 10)
        v_lay.setSpacing(10)
        self.setLayout(v_lay)

        t = "Кэшированные изображения."
        title_label = QLabel(t)
        v_lay.addWidget(title_label)

        h_wid = QWidget()
        v_lay.addWidget(h_wid)

        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_wid.setLayout(h_lay)

        self.current_size = QLabel("")
        h_lay.addWidget(self.current_size)

        self.clear_btn = QPushButton("Очистить данные")
        self.clear_btn.clicked.connect(self.clear_db_cmd)
        h_lay.addWidget(self.clear_btn)
        
        self.slider_values = [2, 5, 10, 100]
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(len(self.slider_values) - 1)
        self.slider.setTickPosition(QSlider.TicksBelow)
        self.slider.setTickInterval(1)
        v_lay.addWidget(self.slider)

        self.label = QLabel("", self)
        v_lay.addWidget(self.label)
        self.get_current_size()

        v_lay.addStretch(0)

        current = Config.json_data.get("clear_db")
        ind = self.slider_values.index(current)

        self.slider.setValue(ind)
        self.update_label(ind)
        self.slider.valueChanged.connect(self.update_label)

    def update_label(self, index):
        value = self.slider_values[index]

        if value == 100:
            t = "Максимальный размер данных: без лимита"
        else:
            t = f"Максимальный размер данных: {value}гб"

        self.label.setText(t)
        Config.json_data["clear_db"] = value

    def get_current_size(self):
        with Engine.engine.connect() as conn:
            q = sqlalchemy.select(STATS.c.size).where(STATS.c.name == "main")
            res = conn.execute(q).scalar() or 0

        res = int(res / (1024))
        t = f"Данные: {res}кб"

        if res > 1024:
            res = round(res / (1024), 2)
            t = f"Данные: {res}мб"

        if res > 1024:
            res = round(res / (1024), 2)
            t = f"Данные: {res}гб"

        self.current_size.setText(t)

    def clear_db_cmd(self):
        if Dbase.clear_db():
            self.get_current_size()

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        Config.write_json_data()
    
    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() == Qt.Key.Key_Escape:
            self.close()


class AdvancedBtn(QPushButton):
    open_path = pyqtSignal(str)

    def __init__(self):
        super().__init__("")
        self.setFixedWidth(50)

        menu = QMenu()
        self.setMenu(menu)

        self.go_action = QAction(parent=self, text="Перейти")
        self.go_action.triggered.connect(self.open_go_win)
        menu.addAction(self.go_action)

        self.go_action = QAction(parent=self, text="Настройки")
        self.go_action.triggered.connect(self.open_settings_win)
        menu.addAction(self.go_action)
    
    def open_go_win(self):
        self.win = WinGo()
        self.win.open_path.connect(self.open_path.emit)
        Utils.center_win(Utils.get_main_win(), self.win)
        self.win.show()

    def open_settings_win(self):
        self.win = WinSettings()
        Utils.center_win(Utils.get_main_win(), self.win)
        self.win.show()


class HistoryBtn(QPushButton):
    def __init__(self, text: str):
        super().__init__(text)
        self.setFixedWidth(60)


class BarTop(QFrame):
    back_sig = pyqtSignal(str)
    next_sig = pyqtSignal(str)
    level_up_sig = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setFixedHeight(40)
        self.clmn = 0

        self.root: str = None
        self.history: list[str] = [Config.json_data.get("root")]
        self.current_index: int = 0

        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(10)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.grid_layout)

        self.clmn += 1
        self.back = HistoryBtn("\u25C0")
        self.back.clicked.connect(self.back_cmd)
        self.grid_layout.addWidget(self.back, 0, self.clmn)

        self.clmn += 1
        self.next = HistoryBtn("\u25B6")
        self.next.clicked.connect(self.next_cmd)
        self.grid_layout.addWidget(self.next, 0, self.clmn)

        self.clmn += 1
        self.grid_layout.setColumnStretch(self.clmn, 10)
        self.grid_layout.addItem(QSpacerItem(1, 1), 0, self.clmn)

        # self.clmn += 1
        # self.grid_layout.addItem(QSpacerItem(5, 0), 0, self.clmn)

        self.clmn += 1
        self.level_up_btn = QPushButton("\u2191")
        self.level_up_btn.setFixedWidth(60)
        self.level_up_btn.clicked.connect(self._level_up_cmd)
        self.grid_layout.addWidget(self.level_up_btn, 0, self.clmn)

        # self.clmn += 1
        # self.grid_layout.addItem(QSpacerItem(5, 0), 0, self.clmn)

        self.clmn += 1
        self.view_type_btn = ViewTypeBtn()
        self.grid_layout.addWidget(self.view_type_btn, 0, self.clmn)

        # self.clmn += 1
        # self.grid_layout.addItem(QSpacerItem(5, 0), 0, self.clmn)

        self.clmn += 1
        self.sort_type_btn = SortTypeBtn(parent=self)
        self.grid_layout.addWidget(self.sort_type_btn, 0, self.clmn)

        self.clmn += 1
        self.advanced_btn = AdvancedBtn()
        self.grid_layout.addWidget(self.advanced_btn, 0, self.clmn)

        # self.clmn += 1
        # self.grid_layout.addItem(QSpacerItem(5, 0), 0, self.clmn)

        self.clmn += 1
        self.grid_layout.setColumnStretch(self.clmn, 10)
        self.grid_layout.addItem(QSpacerItem(1, 1), 0, self.clmn)

        self.clmn += 1
        self.search_wid = SearchWidget()
        self.grid_layout.addWidget(self.search_wid, 0, self.clmn)

    def update_history(self):
        topbar = self.sender()
        if isinstance(topbar, BarTop):
            pos = topbar.mapFromGlobal(QCursor.pos())
            if isinstance(topbar.childAt(pos), HistoryBtn):
                return

        self.history.append(Config.json_data.get("root"))
        self.current_index = len(self.history) - 1

        if len(self.history) > 50:
            self.history.pop(0)

    def _level_up_cmd(self):
        Config.json_data["root"] = os.path.dirname(Config.json_data.get("root"))
        self.level_up_sig.emit()

    def back_cmd(self):
        if self.current_index == 0:
            return

        self.current_index -= 1

        try:
            path = self.history[self.current_index]
            self.back_sig.emit(path)
        except IndexError:
            pass

    def next_cmd(self):
        if self.current_index == len(self.history) - 1:
            return
        
        self.current_index += 1

        try:
            path = self.history[self.current_index]
            self.next_sig.emit(path)
        except IndexError:
            pass
