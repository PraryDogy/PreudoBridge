import os

from PyQt5.QtCore import QThread, pyqtSignal


class GetDirItems(QThread):
    get_dir_finished = pyqtSignal(list)
    stop = pyqtSignal()

    def __init__(self, path: str, only_photo: bool):
        super().__init__()
        self.path = path
        self.only_photo = only_photo
        self.flag = True

        self.stop.connect(self.stop_cmd)

    def run(self):
        if os.path.isdir(self.path):
            try:

                directory_items = []

                if self.only_photo:

                    for item in os.listdir(self.path):
                        item: str = os.path.join(self.path, item)
                        if not self.flag:
                            return
                        if os.path.isdir(item):
                            directory_items.append(item)
                        elif item.lower().endswith((".jpg", "jpeg", ".tif", ".tiff", ".psd", ".psb", ".png")):
                            directory_items.append(item)

                else:

                    for item in os.listdir(self.path):
                        if not self.flag:
                            return
                        directory_items.append(os.path.join(self.path, item))

                self.get_dir_finished.emit(directory_items)
                    
            except PermissionError as e:
                pass

    def stop_cmd(self):
        self.flag = False