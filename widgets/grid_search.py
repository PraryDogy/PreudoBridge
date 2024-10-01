import os

import sqlalchemy
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QGridLayout, QWidget, QLabel

from cfg import Config
from database import Cache, Dbase
from fit_img import FitImg
from utils import Utils

from .grid_base import GridBase


class SearchFinderThread(QThread):
    finished = pyqtSignal()
    stop_sig = pyqtSignal()
    new_widget = pyqtSignal(dict)

    def __init__(self, root: str, filename: str):
        super().__init__(self)

        self.filename: str = filename
        self.root: str = root
        self.flag: bool = True
        self.session = Dbase.get_session()

        self.stop_sig.connect(self.stop_cmd)

    def stop_cmd(self):
        self.flag: bool = False

    def run(self):
        for root, dirs, files in os.walk(self.root):

            if not self.flag:
                break

            for file in files:

                if not self.flag:
                    break

                src = os.path.join(root, file)

                if self.filename in file:
                    q = sqlalchemy.select(Cache.img).where(Cache.src==src)
                    res = self.session.execute(q).first()
                    if res:
                        pixmap: QPixmap = Utils.pixmap_from_bytes(res[0])
                    else:
                        img = Utils.read_image(src)
                        img = FitImg.start(img)
                        if img:
                            pixmap = Utils.pixmap_from_array(img)
                            db_img = Utils.image_array_to_bytes(img)

                            try:
                                stats = os.stat(src)
                            except (PermissionError, FileNotFoundError):
                                continue

                            size = stats.st_size
                            modified = stats.st_mtime

                            q = sqlalchemy.insert(Cache)
                            q = q.values({
                                "img": db_img,
                                "src": src,
                                "root": self.root,
                                "size": size,
                                "modified": modified
                                })
                            self.session.execute(q)
                        else:
                            pixmap = QPixmap("images/file_210.png")

                    self.new_widget.emit({"src": src, "pixmap": pixmap})
        self.session.commit()


class GridSearch(GridBase):
    def __init__(self, width: int, search_text: str):
        super().__init__()
        self.setWidgetResizable(True)

        Config.img_viewer_images.clear()

        self.clmn_count = width // Config.thumb_size
        if self.clmn_count < 1:
            self.clmn_count = 1

        self.row, self.col = 0, 0

        main_wid = QWidget()
        self.grid_layout = QGridLayout(main_wid)
        self.grid_layout.setSpacing(5)
        self.setWidget(main_wid)

        self.test = SearchFinderThread(Config.json_data["root"], search_text)
        self.test.new_widget.connect(self.add_new_widget)

    def add_new_widget(self, data: dict):
        widget = QLabel()
        widget.setPixmap(data["widget"])
        self.grid_layout.addWidget(widget)

        self.col += 1
        if self.col >= self.clmn_count:
            self.col = 0
            self.row += 1