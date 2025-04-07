import os
import shutil

from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtWidgets import QLabel, QProgressBar, QPushButton, QHBoxLayout, QVBoxLayout, QWidget

from cfg import Dynamic, JsonData, Static
from signals import SignalsApp
from utils import URunnable, UThreadPool

from ._base import USvgWidget, WinMinMax

PREPARING_T = "Подготовка"
COPYING_T = "Копирую файлы"
CANCEL_T = "Отмена"


class WorderSignals(QObject):
    finished_ = pyqtSignal(list)  # Сигнал с результатами (новыми путями к файлам)
    progress = pyqtSignal(int)  # Сигнал для передачи значения прогрессбара
    progress_text = pyqtSignal(str)
    total = pyqtSignal(int)  # Сигнал для передачи суммарного значения прогрессбара

class FileCopyWorker(URunnable):
    def __init__(self):
        super().__init__()
        self.signals_ = WorderSignals()

    @URunnable.set_running_state
    def run(self):    
        new_paths = self.create_new_paths()
        total = len(new_paths)
        try:
            self.signals_.total.emit(total)
        except RuntimeError:
            ...

        for x, (old_filepath, new_filepath) in enumerate(new_paths, start=1):

            if not self.should_run:
                break
            
            try:
                self.signals_.progress.emit(x)
                self.signals_.progress_text.emit(f"{COPYING_T} {x} из {total}")
            except RuntimeError:
                ...

            new_folders, tail = os.path.split(new_filepath)
            os.makedirs(new_folders, exist_ok=True)

            try:
                shutil.copy2(old_filepath, new_filepath)
            except Exception as e:
                print("win copy files > copy file error", e)
                continue

        # создаем список путей к виджетам в сетке для выделения
        paths_for_selection = self.collapse_to_root_dirs(new_paths, JsonData.root)

        try:
            self.signals_.finished_.emit(list(paths_for_selection))
        except RuntimeError:
            ...
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
        self.setFixedSize(280, 55)
        self.setWindowTitle(COPYING_T)

        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(15, 5, 15, 5)
        v_lay.setSpacing(0)
        self.setLayout(v_lay)

        first_row = QWidget()
        v_lay.addWidget(first_row)
        first_lay = QHBoxLayout()
        first_lay.setContentsMargins(0, 0, 0, 0)
        first_row.setLayout(first_lay)

        lbl = QLabel(text=PREPARING_T)
        first_lay.addWidget(lbl)

        second_row = QWidget()
        v_lay.addWidget(second_row)
        second_lay = QHBoxLayout()
        second_lay.setContentsMargins(0, 0, 0, 0)
        second_lay.setSpacing(10)
        second_row.setLayout(second_lay)

        progressbar = QProgressBar()
        second_lay.addWidget(progressbar)

        cancel_btn = USvgWidget(src=Static.CLEAR_SVG, size=16)
        cancel_btn.mouseReleaseEvent = self.cancel_cmd
        second_lay.addWidget(cancel_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.task_ = None

        if Dynamic.files_to_copy:
            self.task_ = FileCopyWorker()
            self.task_.signals_.total.connect(progressbar.setMaximum)
            self.task_.signals_.progress.connect(progressbar.setValue)
            self.task_.signals_.progress_text.connect(lbl.setText)
            self.task_.signals_.finished_.connect(self.finished_task)
            UThreadPool.start(runnable=self.task_)

    def cancel_cmd(self, *args):
        self.close()

    def finished_task(self, new_paths: list[str]):
        self.close()
        SignalsApp.instance.load_standart_grid.emit((JsonData.root, new_paths))
        del self.task_

    def closeEvent(self, a0):
        if self.task_:
            self.task_.should_run = False
        self.close()