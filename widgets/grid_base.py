from PyQt5.QtWidgets import QScrollArea


class GridBase(QScrollArea):
    def __init__(self):
        super().__init__()

    def stop_and_wait_threads(self):
        print("abstact method: stop_and_wait_threads")

    def stop_threads(self):
        print("abstact method: stop_threads")
