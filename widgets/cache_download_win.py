import os

from PyQt5.QtCore import Qt

from cfg import Static
from system.tasks import CacheDownloader, UThreadPool

from .progressbar_win import ProgressbarWin


class CacheDownloadWin(ProgressbarWin):
    title = "Кэширование папки"
    preparing_text = "Ищу изображения"
    caching_text = "Кэширование"
    svg_path = os.path.join(Static.icons_rel_dir, "warning.svg")

    def __init__(self, dirs: list[str]):
        super().__init__(self.title, self.svg_path)
        # self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.dirs = dirs
        self.start_task()

    def start_task(self):
        # алгоритм действий
        # прогрессбар стоит на месте, верхний лейбл Подготовка
        # нижний лейбл - имена файлов при обходе директорий
        # верхний лейбл Кэширование
        # нижний лейбл 1 из 100 
        self.tsk = CacheDownloader(self.dirs)

        # этап подготовки (обход директорий)
        self.above_label.setText(self.preparing_text)
        self.tsk.sigs.filename.connect(
            lambda filename: self.below_label.setText(filename)
        )

        # этап кэширования
        self.tsk.sigs.caching.connect(
            lambda: self.above_label.setText(self.caching_text)
        )
        self.tsk.sigs.prorgess_max.connect(
            lambda v: self.progressbar.setMaximum(v)
        )
        self.tsk.sigs.progress.connect(
            lambda v: self.progressbar.setValue(v)
        )
        self.tsk.sigs.progress_txt.connect(
            lambda text: self.below_label.setText(text)
        )
        self.tsk.sigs.finished_.connect(
            lambda: self.deleteLater()
        )

        # text = "".join((str(i) for i in range(1, 100)))
        # self.below_label.setText(self.tsk.cut_filename(text))
        UThreadPool.start(self.tsk)

    def deleteLater(self):
        # Кнопка cancel запускает deleteLater, здесь мы его и перехватываем
        try:
            self.tsk.set_should_run(False)
        except Exception as e:
            print("CacheDownloadWin error", e)
        return super().deleteLater()
    
    def closeEvent(self, a0):
        try:
            self.tsk.sigs.finished_.disconnect()
            self.tsk.set_should_run(False)
        except Exception as e:
            print("CacheDownloadWin error", e)
        return super().closeEvent(a0)