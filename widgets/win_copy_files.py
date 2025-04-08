import os
import shutil

from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtWidgets import QLabel, QProgressBar, QPushButton, QHBoxLayout, QVBoxLayout, QWidget

from cfg import Dynamic, JsonData, Static
from signals import SignalsApp
from utils import URunnable, UThreadPool, Utils

from ._base import USvgSqareWidget, WinMinMax

PREPARING_T = "Подготовка"
COPYING_T = "Копирую файлы"
CANCEL_T = "Отмена"


class WorderSignals(QObject):
    finished_ = pyqtSignal(list)  # Сигнал с результатами (новыми путями к файлам)
    set_value_progress = pyqtSignal(int)  # Сигнал для передачи значения прогрессбара
    set_text_progress = pyqtSignal(str)
    set_max_progress = pyqtSignal(int)  # Сигнал для передачи суммарного значения прогрессбара

class FileCopyWorker(URunnable):
    def __init__(self):
        super().__init__()
        self.signals_ = WorderSignals()

    @URunnable.set_running_state
    def run(self):    
        new_paths = self.create_new_paths()

        total_bytes = sum([os.path.getsize(old_path)for old_path, new_path in new_paths])
        total_mb = int(total_bytes / (1024 * 1024))
        try:
            self.signals_.set_max_progress.emit(total_mb)
        except RuntimeError:
            ...

        self.copied_bytes = 0
        self.total_f_size = Utils.get_f_size(total_bytes)

        for src, dest in new_paths:

            if not self.should_run:
                break
            
            new_folders, tail = os.path.split(dest)
            os.makedirs(new_folders, exist_ok=True)

            try:
                # shutil.copy2(old_filepath, new_filepath)
                self.copy_by_bytes(src, dest)
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

    def copy_by_bytes(self, src: str, dest: str):
        buffer_size = 1024 * 1024  # 1 MB

        try:
            with open(src, 'rb') as fsrc, open(dest, 'wb') as fdest:
                while self.should_run:
                    buf = fsrc.read(buffer_size)
                    if not buf:
                        break
                    fdest.write(buf)
                    self.copied_bytes += len(buf)
                    self.report_progress()
        except Exception as e:
            print(e)

    def report_progress(self):
        try:
            copied_mb = int(self.copied_bytes / (1024 * 1024))
            self.signals_.set_value_progress.emit(copied_mb)
            copied_f_size = Utils.get_f_size(self.copied_bytes)
            self.signals_.set_text_progress.emit(f"{COPYING_T} {copied_f_size} из {self.total_f_size}")
        except RuntimeError:
            ...

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
        return (file, os.path.join(dest, filename))

    def scan_folder(self, src_dir: str, dest: str):
        """
        Рекурсивно сканирует папку src_dir.
        Возвращает список кортежей: (путь к исходному файлу, путь назначения).

        Путь назначения формируется так:
        - Берётся относительный путь файла относительно родительской папки src_dir
        - Этот относительный путь добавляется к пути назначения dest
        """

        stack = [src_dir]
        new_paths: list[tuple[str, str]] = []

        src_dir = os.sep + src_dir.strip(os.sep)
        dest = os.sep + dest.strip(os.sep)

        # Родительская папка от src_dir — нужна, чтобы определить
        # относительный путь каждого файла внутри src_dir
        parent = os.path.dirname(src_dir)

        while stack:
            current_dir = stack.pop()
            for dir_entry in os.scandir(current_dir):
                if dir_entry.is_dir():
                    stack.append(dir_entry.path)
                else:
                    rel_path = dir_entry.path.split(parent)[-1]
                    new_path = dest + rel_path
                    new_paths.append((dir_entry.path, new_path))

        return new_paths


class WinCopyFiles(WinMinMax):
    finished_ = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setFixedSize(400, 75)
        self.setWindowTitle(COPYING_T)

        main_lay = QHBoxLayout()
        main_lay.setContentsMargins(10, 5, 10, 5)
        main_lay.setSpacing(5)
        self.setLayout(main_lay)

        left_side_icon = USvgSqareWidget(src=Static.COPY_FILES_SVG, size=50)
        main_lay.addWidget(left_side_icon)

        right_side_wid = QWidget()
        right_side_lay = QVBoxLayout()
        right_side_lay.setContentsMargins(0, 0, 0, 0)
        right_side_lay.setSpacing(0)
        right_side_wid.setLayout(right_side_lay)
        main_lay.addWidget(right_side_wid)

        right_side_lay.addStretch()

        first_row = QWidget()
        right_side_lay.addWidget(first_row)
        first_lay = QHBoxLayout()
        first_lay.setContentsMargins(0, 0, 0, 0)
        first_row.setLayout(first_lay)

        lbl = QLabel(text=PREPARING_T)
        first_lay.addWidget(lbl)

        second_row = QWidget()
        right_side_lay.addWidget(second_row)
        second_lay = QHBoxLayout()
        second_lay.setContentsMargins(0, 0, 0, 0)
        second_lay.setSpacing(10)
        second_row.setLayout(second_lay)

        progressbar = QProgressBar()
        second_lay.addWidget(progressbar)

        cancel_btn = USvgSqareWidget(src=Static.CLEAR_SVG, size=16)
        cancel_btn.mouseReleaseEvent = self.cancel_cmd
        second_lay.addWidget(cancel_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        right_side_lay.addStretch()

        self.task_ = None

        if Dynamic.files_to_copy:
            self.task_ = FileCopyWorker()
            self.task_.signals_.set_max_progress.connect(lambda value: self.test(progressbar, value))
            self.task_.signals_.set_value_progress.connect(lambda value: self.test_rwo(progressbar, value))
            self.task_.signals_.set_text_progress.connect(lbl.setText)
            self.task_.signals_.finished_.connect(self.finished_task)
            UThreadPool.start(runnable=self.task_)

    def test(self, progress: QProgressBar, value):
        progress.setMaximum(abs(value))

    def test_rwo(self, progress: QProgressBar, value):
        progress.setValue(value)

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