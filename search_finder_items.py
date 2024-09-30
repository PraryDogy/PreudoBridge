import os

import sqlalchemy
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QPixmap

from cfg import Config
from database import Cache, Dbase
from utils import PixmapFromBytes


class SearchFinderThread(QThread):
    finished = pyqtSignal()
    stop_sig = pyqtSignal()
    new_widget = pyqtSignal(dict)

    def __init__(self, root: str, filename: str):
        super().__init__(self)

        self.filename: str = filename
        self.root: str = root
        self.flag: bool = True

        self.stop_sig.connect(self.stop_cmd)

    def stop_cmd(self):
        self.flag: bool = False

    def run(self):
        session = Dbase.get_session()

        for root, dirs, files in os.walk(self.root):
            for file in files:

                src = os.path.join(root, file)

                if file == self.filename:

                    q = sqlalchemy.select(Cache.img).where(Cache.src==src)
                    res = session.execute(q).first()

                    if res:
                        pixmap: QPixmap = PixmapFromBytes(res[0])
                    else:
                        ...




                    ...
                    self.new_widget.emit(
                        {
                            "src": os.path.join(root, file),
                            "pixmap": pixmap
                            }
                            )