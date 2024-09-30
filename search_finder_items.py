import os

import sqlalchemy
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QPixmap

from cfg import Config
from database import Cache, Dbase
from fit_img import FitImg
from utils import Utils


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
                        pixmap: QPixmap = Utils.pixmap_from_bytes(res[0])
                    else:
                        img = Utils.read_image(src)
                        img = FitImg.start(img)
                        if img:
                            pixmap = Utils.pixmap_from_array(img)
                            db_img = Utils.image_array_to_bytes(img)
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


                    self.new_widget.emit(
                        {
                            "src": os.path.join(root, file),
                            "pixmap": pixmap
                            }
                            )