from cfg import Static
from system.tasks import ArchiveTask
from system.utils import UThreadPool
from PyQt5.QtCore import pyqtSignal, QTimer
from .progressbar_win import ProgressbarWin


class ArchiveWin(ProgressbarWin):
    finished_ = pyqtSignal()
    title = "Архив"
    below_text = "Подготовка"
    above_text = "Создание архива..."

    def __init__(self, files: list[str], zip_path: str):
        super().__init__(self.title, Static.COPY_FILES_SVG)
        self.set_modality()
        self.above_label.setText(self.above_text)
        self.below_label.setText(self.below_text)

        self.archive_task = ArchiveTask(files, zip_path)
        self.archive_task.sigs.set_max.connect(self.progressbar.setMaximum)
        self.archive_task.sigs.set_value.connect(self.set_value)
        self.archive_task.sigs.finished_.connect(self.finalize)
        QTimer.singleShot(200, lambda: UThreadPool.start(self.archive_task))
    
    def set_value(self, value: int):
        self.below_label.setText(f"Архивирую {value} из {self.progressbar.maximum()}")
        self.progressbar.setValue(value)

    def cancel_cmd(self, *args):
        self.archive_task.set_should_run(False)
        return super().cancel_cmd(*args)
    
    def finalize(self, *args):
        self.finished_.emit()
        self.cancel_cmd()