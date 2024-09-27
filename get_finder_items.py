import os

from PyQt5.QtCore import QThread, pyqtSignal

from cfg import Config


class GetFinderItemsThread(QThread):
    finished = pyqtSignal(list)
    stop = pyqtSignal()

    def __init__(self, root: str):
        super().__init__()
        self.root = root
        self.flag = True
        self.finder_items: dict = {}

        self.stop.connect(self.stop_cmd)

    def run(self):
        try:
            self.__get_items()
            self.__sort_items()
        except PermissionError:
            self.finder_items: dict = {}
        
        self.finished.emit(self.finder_items)

    def __get_items(self):
        for item in os.listdir(self.root):
            src: str = os.path.join(self.root, item)

            if not self.flag:
                break

            filename = src.split(os.sep)[-1]
            stats = os.stat(src)
            size = stats.st_size
            modified = stats.st_mtime
            filetype = os.path.splitext(filename)[1]

            if Config.json_data["only_photo"]:
                if src.lower().endswith(self.img_ext):
                    self.finder_items[(src, filename, size, modified, filetype)] = None
                    continue
            else:
                self.finder_items[(src, filename, size, modified, filetype)] = None


    def __sort_items(self):
        sort_data = {"name": 1, "size": 2,  "modify": 3, "type": 4}
        # начинаем с 1, потому что 0 у нас src, нам не нужна сортировка по src

        index = sort_data.get(Config.json_data["sort"])
        self.finder_items = dict(
            sorted(self.finder_items.items(), key=lambda item: item[0][index])
            )

        if Config.json_data["reversed"]:
            self.finder_items = dict(reversed(self.finder_items.items()))

    def stop_cmd(self):
        self.flag = False