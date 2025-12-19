import os

from PyQt5.QtCore import pyqtSignal, QTimer

from cfg import Static
from system.tasks import ToJpegConverter, UThreadPool

from .progressbar_win import ProgressbarWin


class ImgConvertWin(ProgressbarWin):
    title_text = "Создаю копии jpg"
    prepairing = "Подготовка..."

    def __init__(self, urls: list[str]):
        super().__init__(self.title_text, os.path.join(Static.internal_icons_dir, "files.svg"))
        self.progressbar.setMinimum(0)
        self.urls = urls

        self.cancel_btn.clicked.connect(self.cancel_cmd)
        self.above_label.setText(self.prepairing)
        self.below_label.setText(f"0 из {len(urls)}")

        if urls:
            self.tsk_ = ToJpegConverter(urls)
            self.tsk_.sigs.finished_.connect(lambda urls:self.finished_cmd(urls))
            self.progressbar.setMaximum(len(urls))
            UThreadPool.start(self.tsk_)

            self.timer_ = QTimer(self)
            self.timer_.timeout.connect(self.update_gui)
            self.timer_.start(500)

    def update_gui(self, limit: int = 30):
        if len(self.tsk_.current_filename) > limit:
            filename = self.tsk_.current_filename[:limit] + "..."
        else:
            filename = self.tsk_.current_filename
        self.above_label.setText(filename)

        self.below_label.setText(f"{self.tsk_.current_count} из {self.tsk_.total_count}")
        self.progressbar.setValue(self.tsk_.current_count)

    def finished_cmd(self, urls: list[str]):
        self.timer_.stop()
        self.deleteLater()

    def cancel_cmd(self):
        self.tsk_.set_should_run(False)
        self.timer_.stop()
        self.deleteLater()