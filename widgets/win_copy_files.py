import os
import shutil

from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtWidgets import QLabel, QPushButton, QVBoxLayout

from cfg import Dynamic, JsonData, Static
from signals import SignalsApp
from utils import URunnable, UThreadPool

from ._base import WinMinMax

PREPARING_T = "Подготовка"
COPYING_T = "Копирую файлы"
CANCEL_T = "Отмена"


class WorderSignals(QObject):
    finished_ = pyqtSignal(list)  # Сигнал с результатами (новыми путями к файлам)
    progress = pyqtSignal(str)  # Сигнал для передачи статуса копирования
    same_place = pyqtSignal()

class FileCopyWorker(URunnable):
    def __init__(self):
        super().__init__()
        self.signals_ = WorderSignals()

    @URunnable.set_running_state
    def run(self):    
        new_paths = self.create_new_paths()
        total = len(new_paths)

        for x, (old_filepath, new_filepath) in enumerate(new_paths, start=1):

            if not self.should_run:
                break

            new_folders, tail = os.path.split(new_filepath)
            os.makedirs(new_folders, exist_ok=True)

            try:
                shutil.copy2(old_filepath, new_filepath)
            except Exception as e:
                print("win copy files > copy file error", e)
                continue

        # создаем список путей к виджетам в сетке для выделения
        paths_for_selection = self.collapse_to_root_dirs(new_paths, JsonData.root)

        self.signals_.finished_.emit(list(paths_for_selection))
        Dynamic.files_to_copy.clear()

    def collapse_to_root_dirs(self, new_paths: list[tuple[str, str]], root: str):
        result = set()
        for old_path, new_path in new_paths:
            rel = os.path.relpath(new_path, root)
            first_part = rel.split(os.sep)[0]
            result.add(os.path.join(root, first_part))
        return result

    def create_new_paths(self):
        new_paths: list[tuple[str, str]] = []

        for i in Dynamic.files_to_copy:
            i = os.sep + i.strip(os.sep)
            if os.path.isdir(i):
                new_paths.extend(self.scan_folder(i, JsonData.root))
            else:
                new_paths.append(self.single_file(i, JsonData.root))

        return new_paths

    def single_file(self, file: str, dest: str):
        """
        Возвращает кортеж: исходный путь файла, финальный путь файла
        """
        filename = os.path.basename(file)
        return (file, os.path.join(dest, filename)
)
    def scan_folder(self, folder: str, dest: str):
        """
        Рекурсивно сканирует заданную папку (folder).   
        Возвращает список кортежей: исходный путь файла,
        финальный путь (dest: куда копировать файл).
        """
        stack = [folder]
        file_paths: list[tuple[str, str]] = []

        while stack:
            current_fir = stack.pop()
            for entry in os.scandir(current_fir):
                if entry.is_dir():
                    stack.append(entry.path)
                else:
                    # Получаем родительскую директорию исходного пути
                    # В данном случае это путь к директории, в которой находится исходная папка folder
                    parent = os.path.dirname(folder)
                    
                    # Получаем относительный путь от исходной директории до текущего файла
                    # Этот шаг нужен, чтобы понять, как файл "расположен" относительно папки folder
                    rel_path = os.path.relpath(entry.path, parent)
                    
                    # Формируем полный путь для назначения
                    # Здесь мы соединяем путь назначения (dest_dir) с относительным путем,
                    # полученным в предыдущем шаге, чтобы сохранить структуру директорий
                    full_dest = os.path.join(dest, rel_path)
                    file_paths.append((entry.path, full_dest))

        return file_paths


class WinCopyFiles(WinMinMax):
    finished_ = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)
        self.setFixedSize(250, 70)
        self.setWindowTitle(COPYING_T)

        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(10, 10, 10, 10)
        v_lay.setSpacing(10)
        self.setLayout(v_lay)

        self.copy_label = QLabel(text=PREPARING_T)
        v_lay.addWidget(self.copy_label)

        self.cancel_btn = QPushButton(text=CANCEL_T)
        self.cancel_btn.clicked.connect(self.cancel_cmd)
        self.cancel_btn.setFixedWidth(100)
        v_lay.addWidget(self.cancel_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.task_ = None

        if Dynamic.files_to_copy:
            self.task_ = FileCopyWorker()
            self.task_.signals_.progress.connect(self.set_progress)
            self.task_.signals_.finished_.connect(self.finished_task)
            self.task_.signals_.same_place.connect(self.cancel_cmd)
            UThreadPool.start(runnable=self.task_)

    def cancel_cmd(self, *args):
        if self.task_:
            self.task_.should_run = False
        self.close()

    def finished_task(self, new_paths: list[str]):
        SignalsApp.instance.load_standart_grid.emit((JsonData.root, new_paths))
        del self.task_
        self.close()

    def set_progress(self, text: str):
        self.copy_label.setText(text)