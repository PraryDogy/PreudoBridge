import os

from PyQt5.QtCore import QTimer

from cfg import Static
from system.multiprocess import ProcessWorker, ToJpegConverter

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
            self.progressbar.setMaximum(len(urls))

            self.tsk_ = ProcessWorker(
                target=ToJpegConverter.start,
                args=(urls, )
            )
            self.tsk_.start()
            QTimer.singleShot(100, self.poll_task)

    def poll_task(self):
        q = self.tsk_.get_queue()
        if not q.empty():
            result = q.get()
            self.above_label.setText(result["filename"])
            self.below_label.setText(f'{result["count"]} из {result["total_count"]}')
            self.progressbar.setValue(result["count"])

        if not self.tsk_.proc.is_alive():
            self.tsk_.terminate()
            self.deleteLater()
        else:
            QTimer.singleShot(400, self.poll_task)

    def cancel_cmd(self):
        self.tsk_.terminate()
        self.deleteLater()