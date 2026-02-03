import os

from PyQt5.QtCore import QTimer

from cfg import Static
from system.items import JpgConvertItem
from system.multiprocess import JpgConverter, ProcessWorker

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
        self.below_label.setText(f"0 из {len(self.urls)}")

        if not urls:
            return

        self.progressbar.setMaximum(len(self.urls))
        jpg_item = JpgConvertItem(self.urls)
        self.jpg_task = ProcessWorker(target=JpgConverter.start, args=(jpg_item, ))

        self.jpg_timer = QTimer(self)
        self.jpg_timer.setSingleShot(True)
        self.jpg_timer.timeout.connect(self.poll_task)

        self.jpg_task.start()
        self.jpg_timer.start(self.jpg_timer_ms)

    def poll_task(self):
        self.jpg_timer.stop()
        q = self.jpg_task.proc_q
        finished = False
        if not q.empty():
            jpg_item: JpgConvertItem = q.get()
            self.above_label.setText(jpg_item.current_filename)
            self.below_label.setText(f'{jpg_item.current_count} из {len(self.urls)}')
            self.progressbar.setValue(jpg_item.current_count)

            if jpg_item.msg == "finished":
                finished = True

        if not self.jpg_task.is_alive() or finished:
            self.progressbar.setValue(self.progressbar.maximum())
            self.below_label.setText(f'{len(self.urls)} из {len(self.urls)}')
            self.jpg_task.terminate()
            self.deleteLater()
        else:
            self.jpg_timer.start(self.jpg_timer_ms)

    def cancel_cmd(self):
        self.deleteLater()

    def closeEvent(self, a0):
        self.jpg_timer.stop()
        self.jpg_task.terminate()
        return super().closeEvent(a0)

    def deleteLater(self):
        self.jpg_timer.stop()
        self.jpg_task.terminate()
        return super().deleteLater()