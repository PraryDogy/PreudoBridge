import os

from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtWidgets import (QHBoxLayout, QLabel, QProgressBar, QPushButton,
                             QVBoxLayout, QWidget)

from cfg import Static
from utils import Utils

from ._base_items import (MainWinItem, MinMaxDisabledWin, URunnable,
                          USvgSqareWidget, UThreadPool)


class WorkerSignals(QObject):
    finished_ = pyqtSignal(list)
    set_value = pyqtSignal(int)
    set_size_mb = pyqtSignal(str)
    set_max = pyqtSignal(int)
    error_ = pyqtSignal()


class FileCopyWorker(URunnable):
    def __init__(self, dest: str, urls: list[str]):
        super().__init__()
        self.dest = dest
        self.urls = urls
        self.signals_ = WorkerSignals()

    def task(self): 
        try:
            new_paths = self.create_new_paths()
        except OSError as e:
            Utils.print_error(e)
            try:
                self.signals_.error_.emit()
            except RuntimeError as e:
                # прерываем процесс, если родительский виджет был уничтожен
                Utils.print_error(e)
                return

        # общий размер всех файлов в байтах
        total_bytes = sum([os.path.getsize(old_path)for old_path, new_path in new_paths])

        # общий размер всех файлов в МБ для установки максимального
        # значения QProgressbar (в байтах плохо работает)
        total_mb = int(total_bytes / (1024 * 1024))

        try:
            self.signals_.set_max.emit(total_mb)
        except RuntimeError as e:
            Utils.print_error(e)
            return

        # сколько уже скопировано в байтах
        self.copied_bytes = 0
        
        # байты переводим в читаемый f string
        self.total_f_size = Utils.get_f_size(total_bytes)

        for src, dest in new_paths:
            # создаем древо папок как в исходной папке
            new_folders, tail = os.path.split(dest)
            os.makedirs(new_folders, exist_ok=True)
            try:
                self.copy_by_bytes(src, dest)
            except IOError as e:
                Utils.print_error(e)
                continue
            except Exception as e:
                Utils.print_error(e)
                self.signals_.error_.emit()
                return

        # создаем список путей к виджетам в сетке для выделения
        paths = self.get_final_paths(new_paths, self.dest)
        paths = list(paths)

        try:
            self.signals_.finished_.emit(paths)
        except RuntimeError as e:
            Utils.print_error(e)

    def copy_by_bytes(self, src: str, dest: str):
        tmp = True
        buffer_size = 1024 * 1024  # 1 MB
        mb_count_update = 5
        report_interval = mb_count_update * 1024 * 1024  # 5 MB
        reported_bytes = 0
        with open(src, 'rb') as fsrc, open(dest, 'wb') as fdest:
            while tmp:
                buf = fsrc.read(buffer_size)
                if not buf:
                    break
                fdest.write(buf)
                # прибавляем в байтах сколько уже скопировано
                self.copied_bytes += len(buf)
                reported_bytes += len(buf)  # <-- вот это добавь

                if reported_bytes >= report_interval:
                    try:
                        self.report_progress()
                    except RuntimeError as e:
                        Utils.print_error(e)
                        return
                    reported_bytes = 0

    def report_progress(self):
        # сколько уже скопировано в байтах переводим в МБ, потому что
        # максимальное число QProgressbar задано тоже в МБ
        copied_mb = int(self.copied_bytes / (1024 * 1024))
        self.signals_.set_value.emit(copied_mb)

        # байты переводим в читаемый f string
        copied_f_size = Utils.get_f_size(self.copied_bytes)

        text = f"{copied_f_size} из {self.total_f_size}"
        self.signals_.set_size_mb.emit(text)

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
        self.old_new_paths: list[tuple[str, str]] = []
        self.new_paths = []

        for i in self.urls:
            i = Utils.normalize_slash(i)
            if os.path.isdir(i):
                self.old_new_paths.extend(self.scan_folder(i, self.dest))
            else:
                src, new_path = self.single_file(i, self.dest)
                if new_path in self.new_paths:
                    new_path = self.add_counter(new_path)
                self.new_paths.append(new_path)
                self.old_new_paths.append((src, new_path))

        return self.old_new_paths
    
    def add_counter(self, path: str):
        counter = 1
        base_root, ext = os.path.splitext(path)
        root = base_root
        while path in self.new_paths:
            path = f"{root} {counter}{ext}"
            counter += 1
        return path

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
    descr_text = "Произошла ошибка при копировании"
    title_text = "Ошибка"
    ok_text = "Ок"
    icon_size = 50

    def __init__(self):
        super().__init__()
        self.set_modality()
        self.setWindowTitle(ErrorWin.title_text)

        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(10, 5, 10, 10)
        main_lay.setSpacing(0)
        self.setLayout(main_lay)

        h_wid = QWidget()
        main_lay.addWidget(h_wid)

        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.setSpacing(10)
        h_wid.setLayout(h_lay)

        warn = USvgSqareWidget(Static.WARNING_SVG, ErrorWin.icon_size)
        h_lay.addWidget(warn)

        test_two = QLabel(ErrorWin.descr_text)
        test_two.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        h_lay.addWidget(test_two)

        ok_btn = QPushButton(ErrorWin.ok_text)
        ok_btn.clicked.connect(self.deleteLater)
        ok_btn.setFixedWidth(90)
        main_lay.addWidget(ok_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.adjustSize()

    def keyPressEvent(self, a0):
        if a0.key() == Qt.Key.Key_Escape:
            self.deleteLater()
        elif a0.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
            self.deleteLater()
        elif a0.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if a0.key() == Qt.Key.Key_Q:
                return
        return super().keyPressEvent(a0)


class CopyFilesWin(MinMaxDisabledWin):
    finished_ = pyqtSignal(list)
    error_ = pyqtSignal()
    preparing_text = "Подготовка"
    title_text = "Копирую файлы"
    progressbar_width = 300
    icon_size = 50

    def __init__(self, dest: str, urls: list[str]):
        super().__init__()
        self.setWindowTitle(CopyFilesWin.title_text)

        main_lay = QHBoxLayout()
        main_lay.setContentsMargins(10, 10, 10, 10)
        main_lay.setSpacing(5)
        self.setLayout(main_lay)

        left_side_icon = USvgSqareWidget(Static.COPY_FILES_SVG, CopyFilesWin.icon_size)
        main_lay.addWidget(left_side_icon)

        right_side_wid = QWidget()
        right_side_lay = QVBoxLayout()
        right_side_lay.setContentsMargins(0, 0, 0, 0)
        right_side_lay.setSpacing(0)
        right_side_wid.setLayout(right_side_lay)
        main_lay.addWidget(right_side_wid)

        src = min(urls, key=len)
        src = os.path.dirname(Utils.normalize_slash(src))
        src = os.path.basename(src)
        src = self.limit_string(src)

        dest_ = os.path.basename(dest)
        dest_ = self.limit_string(dest_)

        src_dest_lbl = QLabel(self.set_text(src, dest_))
        right_side_lay.addWidget(src_dest_lbl)

        progressbar_row = QWidget()
        right_side_lay.addWidget(progressbar_row)
        progressbar_lay = QHBoxLayout()
        progressbar_lay.setContentsMargins(0, 0, 0, 0)
        progressbar_lay.setSpacing(10)
        progressbar_row.setLayout(progressbar_lay)

        self.progressbar = QProgressBar()
        self.progressbar.setTextVisible(False)
        self.progressbar.setFixedHeight(6)
        self.progressbar.setFixedWidth(CopyFilesWin.progressbar_width)
        progressbar_lay.addWidget(self.progressbar)

        cancel_btn = USvgSqareWidget(Static.CLEAR_SVG, 16)
        cancel_btn.mouseReleaseEvent = self.cancel_cmd
        progressbar_lay.addWidget(cancel_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.size_mb_lbl = QLabel(CopyFilesWin.preparing_text)
        right_side_lay.addWidget(self.size_mb_lbl)

        self.adjustSize()

        if urls:
            task_ = FileCopyWorker(dest, urls)
            task_.signals_.set_max.connect(lambda value: self.set_max(value))
            task_.signals_.set_value.connect(lambda value: self.set_value(value))
            task_.signals_.set_size_mb.connect(lambda text: self.size_mb_text(text))
            task_.signals_.finished_.connect(lambda urls: self.on_finished(urls))
            task_.signals_.error_.connect(self.error_.emit)
            UThreadPool.start(task_)

    def size_mb_text(self, text: str):
        self.size_mb_lbl.setText(text)

    def set_text(self, src: str, dest: str):
        return f"Из \"{src}\" в \"{dest}\""

    def limit_string(self, text: str, limit: int = 15):
        if len(text) > limit:
            return text[:limit] + "..."
        return text

    def set_max(self, value):
        try:
            self.progressbar.setMaximum(abs(value))
        except RuntimeError as e:
            Utils.print_error(e)

    def set_value(self, value):
        try:
            self.progressbar.setValue(value)
        except RuntimeError as e:
            Utils.print_error(e)

    def cancel_cmd(self, *args):
        self.deleteLater()

    def on_finished(self, urls: list[str]):
        self.finished_.emit(urls)
        self.deleteLater()
