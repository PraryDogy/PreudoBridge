import os

from PyQt5.QtCore import QTimer

from cfg import Static
from system.tasks import CacheDownloader, UThreadPool

from .progressbar_win import ProgressbarWin


class CacheDownloadWin(ProgressbarWin):
    title = "Кэширование папки"
    preparing_text = "Ищу изображения"
    caching_text = "Кэширование"
    svg_path = os.path.join(Static.internal_icons_dir, "warning.svg")

    def __init__(self, dirs: list[str]):
        super().__init__(self.title, self.svg_path)
        self.dirs = dirs
        self.above_label.setText(self.preparing_text)
        self.below_label.setText("0 из ...")
        self.cancel_btn.clicked.connect(self.on_cancel)

        self.tsk_ = CacheDownloader(self.dirs)
        self.tsk_.sigs.total_count.connect(lambda v: self.progressbar.setMaximum(v))
        self.tsk_.sigs.finished_.connect(self.on_finished)
        UThreadPool.start(self.tsk_)

        self.timer_ = QTimer(self)
        self.timer_.timeout.connect(self.update_gui)
        self.timer_.start(1000)

    def update_gui(self):
        if self.progressbar.maximum() > 0:
            self.above_label.setText(self.limit_string(self.tsk_.current_filename))
            self.below_label.setText(f"{self.tsk_.current_count} из {self.progressbar.maximum()}")

    def limit_string(self, text: str, limit: int = 30):
        if len(text) > limit:
            return text[:limit] + "..."
        return text

    def on_finished(self, *args):
        self.timer_.stop()
        self.deleteLater()

    def on_cancel(self, *args):
        self.tsk_.set_should_run(False)
        self.timer_.stop()
        self.deleteLater()