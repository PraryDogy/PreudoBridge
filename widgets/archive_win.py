import os

from PyQt5.QtCore import QTimer, pyqtSignal

from cfg import Static
from system.tasks import ArchiveMaker, UThreadPool

from .progressbar_win import ProgressbarWin


class ArchiveWin(ProgressbarWin):
    finished_ = pyqtSignal()
    title = "Архив"
    below_text = "Подготовка"
    below_text_sec = "Пожалуйста, подождите"
    above_text = "Создание архива"

    def __init__(self, files: list[str], zip_path: str):
        super().__init__(self.title, Static.app_icons_dir.get("files.svg"))
        # self.set_modality()
        filename = self.limit_string(os.path.basename(zip_path), 30)
        above_text = f"{self.above_text} \"{filename}\""
        self.above_label.setText(above_text)
        self.below_label.setText(self.below_text)

        self.archive_task = ArchiveMaker(files, zip_path)
        self.archive_task.sigs.set_max.connect(self.progressbar.setMaximum)
        self.archive_task.sigs.set_value.connect(self.set_value)
        self.archive_task.sigs.finished_.connect(self.cancel_cmd)
        QTimer.singleShot(200, lambda: UThreadPool.start(self.archive_task))
    
    def set_value(self, value: int):
        self.below_label.setText(self.below_text_sec)
        self.progressbar.setValue(value)

    def cancel_cmd(self, *args):
        self.finished_.emit()
        self.deleteLater()

    def limit_string(self, text: str, limit: int = 15):
        if len(text) > limit:
            return text[:limit] + "..."
        return text