from cfg import Static
from system.tasks import ImgConvertTask
from system.utils import UThreadPool
import subprocess
from .progressbar_win import ProgressbarWin


class ImgConvertWin(ProgressbarWin):
    title_text = "Создаю копии jpg"
    def __init__(self, urls: list[str]):
        super().__init__(self.title_text, Static.COPY_FILES_SVG)
        self.progressbar.setMinimum(0)

        if urls:
            self.img_task = ImgConvertTask(urls)
            self.img_task.signals_.set_progress_len.connect(lambda value: self.progressbar.setMaximum(value))
            self.img_task.signals_.progress_value.connect(lambda value: self.progressbar.setValue(value))
            self.img_task.signals_.finished_.connect(lambda urls:self.finished_(urls))
            UThreadPool.start(self.img_task)

    def finished_(self, urls: list[str]):
        print("fin")
        subprocess.run(["osascript", Static.REVEAL_SCPT] + urls)