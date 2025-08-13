from cfg import Static
from system.tasks import ImgConvertTask
from system.utils import UThreadPool
import subprocess
from .progressbar_win import ProgressbarWin
from PyQt5.QtCore import pyqtSignal

class ImgConvertWin(ProgressbarWin):
    title_text = "Создаю копии jpg"
    finished_ = pyqtSignal(list)

    def __init__(self, urls: list[str]):
        super().__init__(self.title_text, Static.COPY_FILES_SVG)
        self.progressbar.setMinimum(0)
        self.urls = urls

        if urls:
            self.img_task = ImgConvertTask(urls)
            self.img_task.sigs.set_progress_len.connect(lambda value: self.progressbar.setMaximum(value))
            self.img_task.sigs.progress_value.connect(lambda value: self.set_value_cmd(value))
            self.img_task.sigs.finished_.connect(lambda urls:self.finished_cmd(urls))
            UThreadPool.start(self.img_task)

    def set_value_cmd(self, value: int):
        self.above_label.setText(f"{value} из {len(self.urls)}")
        self.progressbar.setValue(value)

    def finished_cmd(self, urls: list[str]):
        # subprocess.run(["osascript", Static.REVEAL_SCPT] + urls)
        self.finished_.emit(urls)