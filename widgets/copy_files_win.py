import os

from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtWidgets import (QHBoxLayout, QLabel, QProgressBar, QPushButton,
                             QVBoxLayout, QWidget)

from cfg import Dynamic, Static
from utils import URunnable, UThreadPool, Utils

from ._base_widgets import USvgSqareWidget, MinMaxDisabledWin

PREPARING_T = "Подготовка"
COPYING_T = "Копирую файлы"
CANCEL_T = "Отмена"
ERROR_DESCR_T = "Произошла ошибка при копировании"
ERROR_TITLE = "Ошибка"


class WorderSignals(QObject):
    finished_ = pyqtSignal(list)
    set_value_progress = pyqtSignal(int)
    set_text_progress = pyqtSignal(str)
    set_max_progress = pyqtSignal(int)
    error_win_sig = pyqtSignal()


class FileCopyWorker(URunnable):
    def __init__(self, main_dir: str):
        super().__init__()
        self.main_dir = main_dir
        self.signals_ = WorderSignals()

    @URunnable.set_running_state
    def run(self):    
        try:
            new_paths = self.create_new_paths()
        except OSError as e:
            print("win copy files", e)
            self.signals_.error_win_sig.emit()
            return

        # общий размер всех файлов в байтах
        total_bytes = sum([os.path.getsize(old_path)for old_path, new_path in new_paths])

        # общий размер всех файлов в МБ для установки максимального
        # значения QProgressbar (в байтах плохо работает)
        total_mb = int(total_bytes / (1024 * 1024))
        try:
            self.signals_.set_max_progress.emit(total_mb)
        except RuntimeError:
            ...

        # сколько уже скопировано в байтах
        self.copied_bytes = 0
        
        # байты переводим в читаемый f string
        self.total_f_size = Utils.get_f_size(total_bytes)

        macintosh_hd = Utils.get_system_volume()

        for src, dest in new_paths:

            if not self.should_run:
                break
            
            # создаем древо папок как в исходной папке
            new_folders, tail = os.path.split(dest)
            os.makedirs(new_folders, exist_ok=True)

            try:
                self.copy_by_bytes(src, dest)

                full_src = Utils.add_system_volume(src)
                full_dest = Utils.add_system_volume(dest)
                if macintosh_hd in full_src and macintosh_hd in full_dest:
                    os.remove(src)

            except Exception as e:
                print("win copy files > copy file error", e)
                continue

        # создаем список путей к виджетам в сетке для выделения
        paths = self.get_final_paths(new_paths, self.main_dir)
        paths = list(paths)
        self.finalize(paths)

    def finalize(self, paths: list[str]):
        try:
            self.signals_.finished_.emit(paths)
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
                    # прибавляем в байтах сколько уже скопировано
                    self.copied_bytes += len(buf)
                    self.report_progress()
        except Exception as e:
            print(e)

    def report_progress(self):
        try:
            # сколько уже скопировано в байтах переводим в МБ, потому что
            # максимальное число QProgressbar задано тоже в МБ
            copied_mb = int(self.copied_bytes / (1024 * 1024))
            self.signals_.set_value_progress.emit(copied_mb)

            # байты переводим в читаемый f string
            copied_f_size = Utils.get_f_size(self.copied_bytes)

            text = f"{copied_f_size} из {self.total_f_size}"
            self.signals_.set_text_progress.emit(text)
        except RuntimeError:
            ...

    def get_final_paths(self, new_paths: list[tuple[str, str]], root: str):
        # Например мы копируем папки test_images и abs_images с рабочего стола в папку загрузок
        # Внутри test_images и abs есть разные файлы и папки
        # 
        # /Users/Some_user/Desktop/test_images/path/to/file.jpg
        # /Users/Some_user/Desktop/test_images/path/to/file 2.jpg
        # /Users/Some_user/Desktop/test_images/path/to/file 2.jpg
        # 
        # /Users/Some_user/Desktop/abs_images/path/to/file.jpg
        # /Users/Some_user/Desktop/abs_imagesges/path/to/file 2.jpg
        # /Users/Some_user/Desktop/abs_images/path/to/file 2.jpg
        # 
        # Наша задача получить сет из следующих элементов:
        # /Users/Some_user/Downloasd/test_images
        # /Users/Some_user/Downloads/abs_image
        # 
        # Сет передается в сигнал finished, где _grid.py выделит виджеты в
        # сетке, соответствующие директориям в сете.
        result = set()
        for old_path, new_path in new_paths:
            rel = os.path.relpath(new_path, root)
            first_part = rel.split(os.sep)[0]
            result.add(os.path.join(root, first_part))
        return result

    def create_new_paths(self):
        new_paths: list[tuple[str, str]] = []

        for i in Dynamic.files_to_copy:
            i = Utils.normalize_slash(i)
            if os.path.isdir(i):
                new_paths.extend(self.scan_folder(i, self.main_dir))
            else:
                new_paths.append(self.single_file(i, self.main_dir))

        return new_paths

    def single_file(self, file: str, dest: str):
        # Возвращает кортеж: исходный путь файла, финальный путь файла
        filename = os.path.basename(file)
        return (file, os.path.join(dest, filename))

    def scan_folder(self, src_dir: str, dest: str):
        # Рекурсивно сканирует папку src_dir.
        # Возвращает список кортежей: (путь к исходному файлу, путь назначения).
        # 
        # Путь назначения формируется так:
        # - Берётся относительный путь файла относительно родительской папки src_dir
        # - Этот относительный путь добавляется к пути назначения dest
        stack = [src_dir]
        new_paths: list[tuple[str, str]] = []

        src_dir = Utils.normalize_slash(src_dir)
        dest = Utils.normalize_slash(dest)

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


class ErrorWin(MinMaxDisabledWin):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(ERROR_TITLE)

        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(10, 10, 10, 10)
        main_lay.setSpacing(0)
        self.setLayout(main_lay)

        h_wid = QWidget()
        main_lay.addWidget(h_wid)

        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.setSpacing(10)
        h_wid.setLayout(h_lay)

        warn = USvgSqareWidget(Static.WARNING_SVG, 50)
        h_lay.addWidget(warn)

        test_two = QLabel(ERROR_DESCR_T)
        h_lay.addWidget(test_two)

        ok_btn = QPushButton("Ок")
        ok_btn.clicked.connect(self.close)
        ok_btn.setFixedWidth(90)
        main_lay.addWidget(ok_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.adjustSize()

    def keyPressEvent(self, a0):
        if a0.key() == Qt.Key.Key_Escape:
            self.close()
        elif a0.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
            self.close()
        return super().keyPressEvent(a0)


class CopyFilesWin(MinMaxDisabledWin):
    load_st_grid_sig = pyqtSignal(tuple)
    error_win_sig = pyqtSignal()

    def __init__(self, main_dir: str):
        super().__init__()
        self.main_dir = main_dir
        self.setFixedSize(400, 75)
        self.setWindowTitle(COPYING_T)

        main_lay = QHBoxLayout()
        main_lay.setContentsMargins(10, 5, 10, 5)
        main_lay.setSpacing(5)
        self.setLayout(main_lay)

        left_side_icon = USvgSqareWidget(Static.COPY_FILES_SVG, 50)
        main_lay.addWidget(left_side_icon)

        right_side_wid = QWidget()
        right_side_lay = QVBoxLayout()
        right_side_lay.setContentsMargins(0, 0, 0, 0)
        right_side_lay.setSpacing(0)
        right_side_wid.setLayout(right_side_lay)
        main_lay.addWidget(right_side_wid)

        right_side_lay.addStretch()

        src = min(Dynamic.files_to_copy, key=len)
        src = os.path.dirname(Utils.normalize_slash(src))
        src = os.path.basename(src)
        dest = os.path.basename(self.main_dir)

        src = self.limit_string(src)
        dest = self.limit_string(dest)

        t = f"Из \"{src}\" в \"{dest}\""
        bottom_lbl = QLabel(t)
        right_side_lay.addWidget(bottom_lbl)

        progressbar_row = QWidget()
        right_side_lay.addWidget(progressbar_row)
        progressbar_lay = QHBoxLayout()
        progressbar_lay.setContentsMargins(0, 0, 0, 0)
        progressbar_lay.setSpacing(10)
        progressbar_row.setLayout(progressbar_lay)

        progressbar = QProgressBar()
        progressbar_lay.addWidget(progressbar)

        cancel_btn = USvgSqareWidget(Static.CLEAR_SVG, 16)
        cancel_btn.mouseReleaseEvent = self.cancel_cmd
        progressbar_lay.addWidget(cancel_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        size_mb_lbl = QLabel(text=PREPARING_T)
        right_side_lay.addWidget(size_mb_lbl)

        right_side_lay.addStretch()

        self.task_ = None

        if Dynamic.files_to_copy:
            self.task_ = FileCopyWorker(self.main_dir)
            self.task_.signals_.set_max_progress.connect(lambda value: self.set_max(progressbar, value))
            self.task_.signals_.set_value_progress.connect(lambda value: self.set_value(progressbar, value))
            self.task_.signals_.set_text_progress.connect(size_mb_lbl.setText)
            self.task_.signals_.finished_.connect(self.finished_task)
            self.task_.signals_.error_win_sig.connect(self.error_win_sig.emit)
            UThreadPool.start(runnable=self.task_)

        self.adjustSize()

    def limit_string(self, text: str, limit: int = 15):
        if len(text) > limit:
            return text[:limit] + "..."
        return text

    def set_max(self, progress: QProgressBar, value):
        progress.setMaximum(abs(value))

    def set_value(self, progress: QProgressBar, value):
        progress.setValue(value)

    def cancel_cmd(self, *args):
        self.close()

    def finished_task(self, new_paths: list[str]):
        self.close()
        self.load_st_grid_sig.emit((self.main_dir, new_paths))
        del self.task_

    def closeEvent(self, a0):
        if self.task_:
            self.task_.should_run = False
        self.close()