from system.tasks import CacheDownloader, UThreadPool

from .progressbar_win import ProgressbarWin


class CacheDownloadWin(ProgressbarWin):
    title = "Кэширование папки"
    preparing_text = "Подготовка"
    svg_path = "./icons/warning.svg"

    def __init__(self, dir: str):
        super().__init__(self.title, self.svg_path)
        self.dir = dir
        self.start_task()

    def start_task(self):
        self.cache_downloader = CacheDownloader(self.dir)
        self.above_label.setText(self.preparing_text)

        self.cache_downloader.sigs.prorgess_max.connect(
            lambda v: self.progressbar.setMaximum(v)
        )
        self.cache_downloader.sigs.progress.connect(
            lambda v: self.progress_win.setValue(v)
        )
        self.cache_downloader.sigs.finished_.connect(
            lambda: self.deleteLater()
        )

        UThreadPool.start(self.cache_downloader)

        # нижний лейбл имя файла

        # верхний лейбл кэширование 1 из 100
        # нижний лейбл имя файла

        # кнопка отмены в окне отменяет таску
        # в таск добавь should run

    def deleteLater(self):
        # Кнопка cancel запускает deleteLater, здесь мы его и перехватываем
        try:
            self.cache_downloader.set_should_run(False)
        except Exception as e:
            print("CacheDownloadWin error", e)
        return super().deleteLater()