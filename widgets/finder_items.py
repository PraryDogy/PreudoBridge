import os
import weakref

import sqlalchemy
from PyQt5.QtCore import QObject, QRunnable, Qt, pyqtSignal
from PyQt5.QtWidgets import QLabel, QWidget
from sqlalchemy.exc import IntegrityError, OperationalError

from cfg import Static
from database import CACHE, Dbase
from utils import Utils

from ._base_items import BaseItem, MainWinItem, SortItem

LOADING_T = "Загрузка..."
SQL_ERRORS = (IntegrityError, OperationalError)
SLEEP_VALUE = 1

class WorkerSignals(QObject):
    finished_ = pyqtSignal(tuple)


class FinderItems(QRunnable):

    def __init__(self, main_win_item: MainWinItem, sort_item: SortItem, parent: QWidget):
        super().__init__()
        self.signals_ = WorkerSignals()
        self.sort_item = sort_item
        self.main_win_item = main_win_item
        self.parent_ref = weakref.ref(parent)

    def run(self):
        try:
            base_items = self.get_base_items()
            conn = self.create_connection()
            if conn:
                base_items, new_items = self.set_rating(conn, base_items)
            else:
                base_items, new_items = self.get_items_no_db()
        except SQL_ERRORS as e:
            Utils.print_error(e)
            base_items, new_items = self.get_items_no_db()
        except Exception as e:
            Utils.print_error(e)
            base_items, new_items = [], []

        base_items = BaseItem.sort_(base_items, self.sort_item)
        new_items = BaseItem.sort_(new_items, self.sort_item)
        try:
            self.signals_.finished_.emit((base_items, new_items))
        except RuntimeError as e:
            Utils.print_error(e)

    def create_connection(self) -> sqlalchemy.Connection | None:
        db = os.path.join(self.main_win_item.main_dir, Static.DB_FILENAME)
        dbase = Dbase()
        engine = dbase.create_engine(path=db)
        if engine is None:
            return None
        else:
            return Dbase.open_connection(engine)

    def set_rating(self, conn: sqlalchemy.Connection, base_items: list[BaseItem]):
        """
        Устанавливает рейтинг для BaseItem, который затем передастся в Thumb    
        Рейтинг берется из базы данных
        """

        stmt = sqlalchemy.select(CACHE.c.name, CACHE.c.rating)
        res = Dbase.execute_(conn, stmt).fetchall()
        res = {name: rating for name, rating in res}

        new_files = []
        for i in base_items:
            name = Utils.get_hash_filename(i.name)
            if name in res:
                i.rating = res.get(name)
            else:
                new_files.append(i)

        return base_items, new_files

    def get_base_items(self) -> list[BaseItem]:
        base_items: list[BaseItem] = []
        with os.scandir(self.main_win_item.main_dir) as entries:
            for entry in entries:
                if entry.name.startswith("."):
                    continue
                item = BaseItem(entry.path)
                item.setup_attrs()
                base_items.append(item)
        return base_items

    def get_items_no_db(self):
        base_items = []
        for entry in os.scandir(self.main_win_item.main_dir):
            if not self.parent_ref():
                break
            if entry.name.startswith("."):
                continue
            if entry.is_dir() or entry.name.endswith(Static.ext_all):
                item = BaseItem(entry.path)
                item.setup_attrs()
                base_items.append(item)
        return base_items, []


class LoadingWid(QLabel):
    def __init__(self, parent: QWidget):
        super().__init__(text=LOADING_T, parent=parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            f"""
                background: {Static.GRAY_GLOBAL};
                border-radius: 4px;
            """
        )

    def center(self, parent: QWidget):
        geo = self.geometry()
        geo.moveCenter(parent.geometry().center())
        self.setGeometry(geo)