import os

from PyQt5.QtCore import QTimer

from cfg import Static
from system.multiprocess import CacheDownloader, ProcessWorker
from .progressbar_win import ProgressbarWin


class CacheDownloadWin(ProgressbarWin):
    title = "Загрузка изображений"
    preparing_text = "Подготовка..."
    svg_path = os.path.join(Static.internal_icons_dir, "warning.svg")

    def __init__(self, dirs: list[str]):
        super().__init__(self.title, self.svg_path)
        self.above_label.setText(self.preparing_text)
        self.cancel_btn.clicked.connect(self.on_cancel)

        self.cache_download_task = ProcessWorker(
            target=CacheDownloader.start,
            args=(dirs, )
        )
        self.cache_download_task.start()
        QTimer.singleShot(100, self.poll_task)

    def poll_task(self):
        q = self.cache_download_task.get_queue()
        maximum = 0
        if not q.empty():
            res = q.get()

            if maximum == 0:
                self.progressbar.setMaximum(res["total_count"])

            self.above_label.setText(res["filename"])
            self.below_label.setText(f'{res["count"]} из {res["total_count"]}')
            self.progressbar.setValue(res["count"])

        if not self.cache_download_task.proc.is_alive():
            self.cache_download_task.terminate()
            self.deleteLater()
        else:
            QTimer.singleShot(100, self.poll_task)

    def on_cancel(self, *args):
        self.cache_download_task.terminate()
        self.deleteLater()

    def deleteLater(self):
        self.cache_download_task.terminate()
        return super().deleteLater()