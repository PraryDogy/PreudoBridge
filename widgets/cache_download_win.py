import os

from PyQt5.QtCore import QTimer

from cfg import Static
from system.multiprocess import CacheDownloader, ProcessWorker
from .progressbar_win import ProgressbarWin


class CacheDownloadWin(ProgressbarWin):
    cache_timer_ms = 300
    title = "Загрузка изображений"
    preparing_text = "Подготовка..."
    svg_path = os.path.join(Static.internal_icons_dir, "warning.svg")

    def __init__(self, dirs: list[str]):
        super().__init__(self.title, self.svg_path)
        self.above_label.setText(self.preparing_text)
        self.cancel_btn.clicked.connect(self.on_cancel)

        self.cache_task = ProcessWorker(
            target=CacheDownloader.start,
            args=(dirs, )
        )

        self.cache_timer = QTimer(self)
        self.cache_timer.timeout.connect(self.poll_task)
        self.cache_timer.setSingleShot(True)

        self.cache_task.start()
        self.cache_timer.start(self.cache_timer_ms)

    def poll_task(self):
        self.cache_timer.stop()
        q = self.cache_task.proc_q
        maximum = 0
        finished = False

        # мы используем if а не while, чтобы gui обновлялся равномерно по таймеру
        if not q.empty():
            res = q.get()

            if res["msg"] == "finished":
                finished = True

            if maximum == 0:
                self.progressbar.setMaximum(res["total_count"])

            self.above_label.setText(res["filename"])
            self.below_label.setText(f'{res["count"]} из {res["total_count"]}')
            self.progressbar.setValue(res["count"])

        if not self.cache_task.is_alive() or finished:
            self.progressbar.setValue(self.progressbar.maximum())
            self.below_label.setText(f'{res["total_count"]} из {res["total_count"]}')
            self.cache_task.terminate()
            self.deleteLater()
        else:
            self.cache_timer.start(self.cache_timer_ms)

    def on_cancel(self, *args):
        self.deleteLater()

    def closeEvent(self, a0):
        self.cache_timer.stop()
        self.cache_task.terminate()
        return super().closeEvent(a0)

    def deleteLater(self):
        self.cache_timer.stop()
        self.cache_task.terminate()
        return super().deleteLater()