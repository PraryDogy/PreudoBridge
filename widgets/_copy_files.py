import os
import shutil

import sqlalchemy
from PyQt5.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from cfg import JsonData, Static
from database import CACHE, Dbase, OrderItem
from signals import SignalsApp
from utils import URunnable, UThreadPool, Utils

from ._grid_tools import GridTools

COPY_TITLE = "Пожалуйста, подождите"
COPY_T = "копирую"
FROM_T = "из"
PREPARING_T = "Подготовка..."
CANCEL_T = "Отмена"
MAX_T = 35


class DbTools:

    @classmethod
    def process_objects(cls, objects: dict[str, int], dest: str):
        
        db = os.path.join(dest, Static.DB_FILENAME)
        dbase = Dbase()
        engine = dbase.create_engine(path=db)

        if engine is None:
            return

        conn = engine.connect()

        for src, rating in objects.items():

            # размер и дату ставим 0, так как новые данные поступят
            # из GridTools

            order_item = OrderItem(
                src = src,
                size = 0,
                mod = 0,
                rating = rating
            )


            print(order_item.__dict__)

            cls.process_item(conn=conn, order_item=order_item)

    @classmethod
    def process_item(cls, conn: sqlalchemy.Connection, order_item: OrderItem):

        filename = os.path.basename(order_item.src)
        q = sqlalchemy.select(CACHE.c.id)
        q = q.where(CACHE.c.name == Utils.hash_filename(filename=filename))
        row_id = conn.execute(q).scalar() or None

        if row_id:
            GridTools.update_file(
                conn=conn,
                order_item=order_item,
                row_id=row_id,
                rating=order_item.rating
            )

        else:
            GridTools.insert_file(
                conn=conn,
                order_item=order_item,
                rating=order_item.rating
            )


class WorkerSignals(QObject):
    progress = pyqtSignal(str)
    finished_ = pyqtSignal(dict)


class CopyFilesThread(URunnable):

    def __init__(self, objects: dict[str, int], dest: str):

        super().__init__()

        self.signals_ = WorkerSignals()
        self.dest = os.sep + dest.strip(os.sep)
        self.counter = 0
        self.objects = objects
        self.new_objects: dict[str, int] = {}

    @URunnable.set_running_state
    def run(self):

        total = len(self.objects)

        for index, (src, rating) in enumerate(self.objects.items(), start=1):

            if not self.should_run:
                self.signals_.finished_.emit(self.counter)
                return

            try:
                path = os.path.join(self.dest, os.path.basename(src))
                new_src = shutil.copy(src, path)
                self.new_objects[new_src] = rating
                self.counter += 1

            except (shutil.SameFileError, IsADirectoryError):
                 ...

            filename = os.path.basename(src)
            t = f"{index} {FROM_T} {total}: {COPY_T} {filename}"

            if len(t) > MAX_T:
                t = t[:MAX_T] + "..."

            self.signals_.progress.emit(t)

        self.signals_.finished_.emit(self.new_objects)

        DbTools().process_objects(
            objects = self.new_objects,
            dest = self.dest
            )


class WinCopyFiles(QWidget):
    def __init__(self, objects: dict[str, int], dest: str):
        super().__init__()

        self.setWindowTitle(COPY_TITLE)
        self.setFixedSize(300, 70)

        self.dest = dest

        fl = Qt.WindowType.Window | Qt.WindowType.CustomizeWindowHint
        fl = fl  | Qt.WindowType.WindowCloseButtonHint
        self.setWindowFlags(fl)

        h_lay = QVBoxLayout(self)
        h_lay.setContentsMargins(15, 10, 15, 10)
        self.setLayout(h_lay)

        self.progress_label = QLabel(text=PREPARING_T)
        h_lay.addWidget(self.progress_label)

        self.cancel_button = QPushButton(text=CANCEL_T)
        self.cancel_button.setFixedWidth(100)
        self.cancel_button.clicked.connect(self.close_thread)
        h_lay.addWidget(self.cancel_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self.task_ = CopyFilesThread(objects=objects,dest=dest)
        self.task_.signals_.progress.connect(self.update_progress)
        self.task_.signals_.finished_.connect(self.on_finished)
        UThreadPool.start(runnable=self.task_)

    def update_progress(self, text: str):
        self.progress_label.setText(text)

    def on_finished(self, objects: dict[str, int]):

        if len(objects) > 0 and JsonData.root == self.dest:

            SignalsApp.instance.load_standart_grid_cmd(
                path=JsonData.root,
                prev_path=None
            )

        QTimer.singleShot(200, self.close)

    def close_thread(self, *args):
        self.task_.should_run = False
        QTimer.singleShot(200, self.close)

    def custom_show(self):

        if self.task_.is_running:
            self.show()