import os

from PyQt5.QtCore import pyqtSignal

from cfg import Static
from system.tasks import ToJpegConverter, UThreadPool

from .progressbar_win import ProgressbarWin


class ImgConvertWin(ProgressbarWin):
    title_text = "Создаю копии jpg"
    finished_ = pyqtSignal(list)

    def __init__(self, urls: list[str]):
        super().__init__(self.title_text, os.path.join(Static.in_app_icons_dir, "files.svg"))
        self.progressbar.setMinimum(0)
        self.urls = urls

        if urls:
            self.img_task = ToJpegConverter(urls)
            self.img_task.sigs.set_progress_len.connect(lambda value: self.progressbar.setMaximum(value))
            self.img_task.sigs.progress_value.connect(lambda value: self.set_value_cmd(value))
            self.img_task.sigs.set_filename.connect(lambda text: self.set_filename(text))
            self.img_task.sigs.finished_.connect(lambda urls:self.finished_cmd(urls))
            UThreadPool.start(self.img_task)

    def set_filename(self, filename: str):
        self.below_label.setText(f"{self.limit_string(filename)}")

    def set_value_cmd(self, value: int):
        self.above_label.setText(f"{value} из {len(self.urls)}")
        self.progressbar.setValue(value)

    def finished_cmd(self, urls: list[str]):
        # subprocess.run(["osascript", Static.REVEAL_SCPT] + urls)
        self.finished_.emit(urls)

    def limit_string(self, text: str, limit: int = 15):
        if len(text) > limit:
            return text[:limit] + "..."
        return text