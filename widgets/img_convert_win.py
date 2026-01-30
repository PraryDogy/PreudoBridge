import os

from PyQt5.QtCore import QTimer

from cfg import Static
from system.multiprocess import ProcessWorker, ToJpegConverter

from .progressbar_win import ProgressbarWin


class ImgConvertWin(ProgressbarWin):
    jpg_timer_ms = 400
    title_text = "Создаю копии jpg"
    prepairing = "Подготовка..."

    def __init__(self, urls: list[str]):
        super().__init__(self.title_text, os.path.join(Static.internal_icons_dir, "files.svg"))
        self.progressbar.setMinimum(0)
        self.urls = urls

        self.cancel_btn.clicked.connect(self.cancel_cmd)
        self.above_label.setText(self.prepairing)
        self.below_label.setText(f"0 из {len(urls)}")

        if not urls:
            return

        self.progressbar.setMaximum(len(urls))

        self.jpg_task = ProcessWorker(
            target=ToJpegConverter.start,
            args=(urls, )
        )

        self.jpg_timer = QTimer(self)
        self.jpg_timer.setSingleShot(True)
        self.jpg_timer.timeout.connect(self.poll_task)

        self.jpg_task.start()
        self.jpg_timer.start(self.jpg_timer_ms)

    def poll_task(self):
        self.jpg_timer.stop()
        q = self.jpg_task.proc_q
        # мы используем if а не while, чтобы gui обновлялся равномерно по таймеру
        if not q.empty():
            result = q.get()
            self.above_label.setText(result["filename"])
            self.below_label.setText(f'{result["count"]} из {result["total_count"]}')
            self.progressbar.setValue(result["count"])

        if not self.jpg_task.is_alive():
            self.jpg_task.terminate()
            self.deleteLater()
        else:
            self.jpg_timer.start(self.jpg_timer_ms)

    def cancel_cmd(self):
        self.deleteLater()

    def deleteLater(self):
        self.jpg_timer.stop()
        self.jpg_task.terminate()
        return super().deleteLater()