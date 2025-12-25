import os

from PyQt5.QtCore import QTimer

from cfg import Static
from system.tasks import CacheDownloader, UThreadPool

from .progressbar_win import ProgressbarWin


class CacheDownloadWin(ProgressbarWin):
    title = "Загрузка изображений"
    preparing_text = "Подготовка..."
    svg_path = os.path.join(Static.internal_icons_dir, "warning.svg")

    def __init__(self, dirs: list[str]):
        super().__init__(self.title, self.svg_path)
        self.dirs = dirs
        self.above_label.setText(self.preparing_text)
        self.cancel_btn.clicked.connect(self.on_cancel)

        self.tsk_ = CacheDownloader(self.dirs)
        self.tsk_.sigs.total_count.connect(self.start_update_gui)
        self.tsk_.sigs.finished_.connect(self.on_finished)
        UThreadPool.start(self.tsk_)

    def start_update_gui(self, value: int):
        self.progressbar.setMaximum(value)
        self.timer_ = QTimer(self)
        self.timer_.timeout.connect(self.update_gui)
        self.timer_.start(1000)

    def update_gui(self):
        if self.progressbar.maximum() > 0:
            self.above_label.setText(self.tsk_.current_filename)
            self.below_label.setText(f"{self.tsk_.current_count} из {self.progressbar.maximum()}")
            self.progressbar.setValue(self.tsk_.current_count)

    def on_finished(self, *args):
        self.timer_.stop()
        self.deleteLater()

    def on_cancel(self, *args):
        self.tsk_.set_should_run(False)
        self.timer_.stop()
        self.deleteLater()