import os
from time import sleep

from PyQt5.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QColor, QPixmap
from PyQt5.QtWidgets import (QFrame, QGraphicsDropShadowEffect, QHBoxLayout,
                             QLabel, QPushButton, QSizePolicy, QVBoxLayout,
                             QWidget)
from sqlalchemy.exc import IntegrityError, OperationalError

from cfg import Dynamic, JsonData, Static, ThumbData
from database import OrderItem
from fit_img import FitImg
from signals import SignalsApp
from utils import URunnable, UThreadPool, Utils

from ._base import USvgWidget, UTextEdit, WinMinMax
from ._grid import COL_COUNT, Grid, Thumb, ThumbSearch

SQL_ERRORS = (IntegrityError, OperationalError)
ATTENTION_T = "Внимание!"
MISSED_FILES = "Не найдены файлы:"
SELECT_ALL_T = "Выделить все"
NO_RESULT = "Ничего не найдено"
SEARCHING = "Идет поиск"
STOP = "Стоп"

class WorkerSignals(QObject):
    new_widget = pyqtSignal(OrderItem)
    finished_ = pyqtSignal()


class SearchFinder(URunnable):
    def __init__(self, search_text: str):
        super().__init__()
        self.signals_ = WorkerSignals()
        self.search_text: str = str(search_text)
        self.extensions: tuple = None
        self.db_path: str = None
        self.conn = None
        self.pause = False

    @URunnable.set_running_state
    def run(self):
        try:
            self.setup_text()
            self.scandir_recursive()
            self.signals_.finished_.emit()
        except RuntimeError as e:
            Utils.print_error(parent=None, error=e)

    def setup_text(self):
        # Ожидается текст из поиска либо в свободной форме,
        # либо в виде шаблона. Проверяем, является ли текст шаблоном
        extensions = Static.SEARCH_EXTENSIONS.get(self.search_text)
        if extensions:
            self.extensions = extensions
            self.process_entry = self.process_extensions

        # Если текст из поиска соотвествует шаблонку "поиск по списку",
        # чтобы искать сразу несколько файлов
        elif self.search_text == Static.SEARCH_LIST_TEXT:
            self.process_entry = self.process_list

        # Простой поиск
        else:
            self.process_entry = self.process_text

    # базовый метод обработки os.DirEntry
    def process_entry(self, entry: os.DirEntry, search_list_lower: list[str]): ...

    def process_extensions(self, entry: os.DirEntry, search_list_lower: list[str]):
        # Поиск файлов с определенным расширением.
        path = entry.path
        path: str = path.lower()
        if path.endswith(self.extensions):
            return True
        else:
            return False

    def process_text(self, entry: os.DirEntry, search_list_lower: list[str]):
        # Поиск файлов с именем.
        filename, _ = os.path.splitext(entry.name)
        filename: str = filename.lower()
        search_text: str = self.search_text.lower()
        if search_text in filename:
            return True
        else:
            return False
        
    def process_list(self, entry: os.DirEntry, search_list_lower: list[str]):
        # Поиск нескольких файлов
        filename, _ = os.path.splitext(entry.name)
        filename_lower: str = filename.lower()
        if filename_lower in search_list_lower:
            return True
        else:
            return False

    def scandir_recursive(self):
        # Инициализируем список с корневым каталогом
        dirs_list = [JsonData.root]

        while dirs_list:
            # Удаляем последний элемент из списка
            # Функция возвращает удаленный элемент
            current_dir = dirs_list.pop()
            if not self.should_run:
                return
            while self.pause:
                sleep(1)
            try:
                # Сканируем текущий каталог и добавляем новые пути в стек
                self.scan_current_dir(dir=current_dir, dirs_list=dirs_list)
            except Exception as e:
                continue

    def scan_current_dir(self, dir: str, dirs_list: list):
        # Формируем список имен файлом в нижнем регистре из SEARCH_LIST.
        # Если SEARCH_LIST пуст, значит осуществляется поиск по расширениям
        # или поиск по тексту
        search_list_lower = [i.lower() for i in Dynamic.SEARCH_LIST]

        with os.scandir(dir) as entries:
            for entry in entries:
                if not self.should_run:
                    return
                while self.pause:
                    sleep(1)
                # Если это директория, добавляем ее в dirs_list, чтобы позже
                # обойти эту директорию в scan_current_dir
                if entry.is_dir():
                    dirs_list.append(entry.path)
                    continue
                # Передаем DirEntry и список имен для обработки в process_enry.
                # При этом неважно, пуст список или нет, т.к. при поиске
                # по списку на process_entry назначается функция, которая
                # сможет обработать этот список, в иных случаях на 
                # process_entry назначаются функции, которые проигнорируют
                # этот список читай setup_text.
                if self.process_entry(entry, search_list_lower):
                    self.process_img(entry=entry)

    def process_img(self, entry: os.DirEntry):
        stat = entry.stat()
        img_array = Utils.read_image(path=entry.path)
        img_array = FitImg.start(
            image=img_array,
            size=ThumbData.DB_IMAGE_SIZE
        )
        pixmap = Utils.pixmap_from_array(image=img_array)
        del img_array
        order_item = OrderItem(
            src=entry.path,
            size=stat.st_size,
            mod=stat.st_mtime,
            rating=0
        )
        order_item.pixmap_ = pixmap
        try:
            self.signals_.new_widget.emit(order_item)
        except Exception as e:
            Utils.print_error(parent=self, error=e)
            self.signals_.new_widget.emit(order_item)
        sleep(0.1)


class WinMissedFiles(WinMinMax):
    def __init__(self, files: list[str]):
        super().__init__()
        self.setWindowTitle(ATTENTION_T)
        self.setMinimumSize(300, 300)
        self.resize(300, 400)

        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(10, 5, 10, 5)
        self.setLayout(v_lay)

        first_row_wid = QWidget()
        v_lay.addWidget(first_row_wid)
        first_row_lay = QHBoxLayout()
        first_row_lay.setContentsMargins(0, 0, 0, 0)
        first_row_wid.setLayout(first_row_lay)

        warn = USvgWidget(src=Static.WARNING_SVG, size=50)
        first_row_lay.addWidget(warn)

        label_ = QLabel(text=MISSED_FILES)
        first_row_lay.addWidget(label_)

        scrollable = UTextEdit()
        scrollable.setText("\n".join(files))
        scrollable.setReadOnly(True)
        scrollable.setCursor(Qt.CursorShape.IBeamCursor)
        v_lay.addWidget(scrollable)

        h_wid = QWidget()
        v_lay.addWidget(h_wid)
        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.setSpacing(10)
        h_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h_wid.setLayout(h_lay)

        ok_btn = QPushButton(text="Ок")
        ok_btn.clicked.connect(self.close)
        ok_btn.setFixedWidth(90)
        h_lay.addWidget(ok_btn)

    def keyPressEvent(self, a0):
        if a0.key() == Qt.Key.Key_Escape:
            self.close()
        return super().keyPressEvent(a0)
    

class TopLabel(QFrame):
    cancel_clicked = pyqtSignal()

    def __init__(self, parent):
        super().__init__(parent=parent)
        self.setObjectName("test")
        self.setStyleSheet(
            f"#test {{ background: {Static.BLUE_GLOBAL}; border-radius: 7px; }}"
        )

        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(5, 0, 5, 0)
        h_lay.setSpacing(10)
        self.setLayout(h_lay)

        label = QLabel(text=SEARCHING)
        label.setFixedHeight(20)
        h_lay.addWidget(label)

        can_btn = QPushButton(text=STOP)
        can_btn.clicked.connect(self.cancel_clicked.emit)
        can_btn.setFixedWidth(90)
        h_lay.addWidget(can_btn)

        self.resize(170, 30)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 150))

        self.setGraphicsEffect(shadow)

class GridSearch(Grid):
    def __init__(self, search_text: str):
        super().__init__()
        self.setAcceptDrops(False)

        self.top_label = TopLabel(parent=self)
        self.top_label.cancel_clicked.connect(self.cancel_cmd)
        self.top_label.show()

        self.col_count = self.width() // Thumb.thumb_w
        self.row, self.col = 0, 0
        self.total = 0

        self.pause_timer = QTimer(self)
        self.pause_timer.timeout.connect(self.remove_pause)
        self.pause_timer.setSingleShot(True)

        SignalsApp.instance.bar_bottom_cmd.emit((JsonData.root, self.total))
        ThumbSearch.calculate_size()

        self.task_ = SearchFinder(search_text)
        self.task_.signals_.new_widget.connect(self.add_new_widget)
        self.task_.signals_.finished_.connect(self.search_fin)
        UThreadPool.start(self.task_)

    def add_new_widget(self, order_item: OrderItem):
        wid = ThumbSearch(
            src=order_item.src,
            size=order_item.size,
            mod=order_item.mod,
            rating=order_item.rating,
            )
        
        if isinstance(order_item.pixmap_, QPixmap):
            wid.set_pixmap(order_item.pixmap_)

        self.add_widget_data(
            wid=wid,
            row=self.row,
            col=self.col
        )

        self.grid_layout.addWidget(wid, self.row, self.col)

        self.total += 1
        self.col += 1
        if self.col >= self.col_count:
            self.col = 0
            self.row += 1
 
        if self.total % 2 == 0:
            SignalsApp.instance.bar_bottom_cmd.emit((None, self.total))

    def search_fin(self):
        SignalsApp.instance.bar_bottom_cmd.emit((None, self.total))
        self.top_label.hide()

        if not self.cell_to_wid:
            no_images = QLabel(text=NO_RESULT)
            no_images.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.addWidget(no_images, 0, 0)

        elif Dynamic.SEARCH_LIST:

            done_src = [
                os.path.splitext(i.name)[0]
                for i in self.cell_to_wid.values()
            ]

            missed_files = [
                i
                for i in Dynamic.SEARCH_LIST
                if i not in done_src
            ]

            if missed_files:
                self.win = WinMissedFiles(files=missed_files)
                Utils.center_win(parent=self.window(), child=self.win)
                self.win.show()

            Dynamic.SEARCH_LIST.clear()

    def order_(self):
        self.task_.pause = True
        self.col_count = self.width() // Thumb.thumb_w
        super().order_()
        self.rearrange()
        self.pause_timer.stop()
        self.pause_timer.start(2000)

    def filter_(self):
        self.task_.pause = True
        super().filter_()
        self.rearrange()
        self.pause_timer.stop()
        self.pause_timer.start(2000)

    def resize_(self):
        self.task_.pause = True
        super().resize_()
        self.rearrange()
        self.pause_timer.stop()
        self.pause_timer.start(2000)

    def rearrange(self):
        # нам нужно вычислить новое количество колонок, актуальную строку
        # и столбец для вставки нового виджета
        self.col_count = self.width() // Thumb.thumb_w
        self.row = len(self.cell_to_wid) // self.col_count
        self.col = len(self.cell_to_wid) % self.col_count
        super().rearrange()

    def remove_pause(self):
        self.task_.pause = False

    def cancel_cmd(self, *args):
        self.top_label.hide()
        self.task_.should_run = False
        self.search_fin()

    def resizeEvent(self, a0):
        x, y = (a0.size().width() // 2) - 100, 10
        self.top_label.move(x, y)
        self.resize_()
        return super().resizeEvent(a0)
    
    def closeEvent(self, a0: QCloseEvent | None) -> None:
        self.task_.should_run = False
        self.task_.pause = False