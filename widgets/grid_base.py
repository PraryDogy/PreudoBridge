from PyQt5.QtCore import QObject


class GridBase(QObject):
    def __init__(self):
        super().__init__()

    def stop_and_wait_threads(self):
        pass

    def stop_threads(self):
        pass


class Test(GridBase):
    def __init__(self):
        super().__init__()