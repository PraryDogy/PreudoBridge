import os
from queue import Empty

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from cfg import Static
from system.items import ClipboardItemGlob
from system.multiprocess import CopyTask, CopyTaskItem, CopyTaskWorker

from ._base_widgets import BtnSmall, UMainWidget
from .win_progressbar import WinProgressbar


class CustomBtn(BtnSmall):
    ww = 75

    def __init__(self, text):
        super().__init__(text)
        self.setStyleSheet("""font-size: 9pt;""")
        self.setFixedWidth(self.ww)


class WinReplaceFiles(UMainWidget):
    descr_text = "Заменить существующие файлы?"
    title_text = "Замена"
    replace_one_text = "Заменить"
    replace_all_text = "Заменить все"
    stop_text = "Стоп"
    ww = 330

    replace_one_press = pyqtSignal()
    replace_all_press = pyqtSignal()
    stop_pressed = pyqtSignal()
    icon_path = os.path.join(Static.internal_images_dir, "warning.svg")
    icon_size = 50

    def __init__(self):
        super().__init__()
        self.set_always_on_top()
        self.set_close_only()
        self.setWindowTitle(self.title_text)
        self.setFixedWidth(self.ww)

        self.central_layout.setContentsMargins(7, 7, 7, 7)
        self.central_layout.setSpacing(0)

        h_wid = QWidget()
        self.central_layout.addWidget(h_wid)

        h_lay = QHBoxLayout(h_wid)
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.setSpacing(10)

        warn = QSvgWidget()
        warn.load(self.icon_path)
        warn.setFixedSize(self.icon_size, self.icon_size)
        h_lay.addWidget(warn)

        test_two = QLabel(self.descr_text)
        test_two.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        h_lay.addWidget(test_two)

        btn_wid = QWidget()
        self.central_layout.addWidget(btn_wid, alignment=Qt.AlignmentFlag.AlignRight)

        btn_lay = QHBoxLayout(btn_wid)
        btn_lay.setContentsMargins(0, 0, 0, 0)
        btn_lay.setSpacing(10)
        btn_lay.setAlignment(Qt.AlignmentFlag.AlignRight)

        btn_lay.addStretch()

        replace_all_btn = CustomBtn(self.replace_all_text)
        replace_all_btn.clicked.connect(lambda: self.replace_all_cmd())
        btn_lay.addWidget(replace_all_btn)

        replace_one_btn = CustomBtn(self.replace_one_text)
        replace_one_btn.clicked.connect(lambda: self.replace_one_cmd())
        btn_lay.addWidget(replace_one_btn)

        stop_btn = CustomBtn(self.stop_text)
        stop_btn.clicked.connect(lambda: self.stop_cmd())
        btn_lay.addWidget(stop_btn)

        self.adjustSize()

    def replace_one_cmd(self):
        self.replace_one_press.emit()

    def replace_all_cmd(self):
        self.replace_all_press.emit()

    def stop_cmd(self):
        self.stop_pressed.emit()

    def closeEvent(self, a0):
        a0.ignore()


class WinError(UMainWidget):
    descr_text = "Произошла ошибка при копировании"
    title_text = "Ошибка"
    ok_text = "Ок"
    icon_path = os.path.join(Static.internal_images_dir, "warning.svg")
    icon_size = 50

    def __init__(self):
        super().__init__()
        self.set_always_on_top()
        self.set_close_only()
        self.setWindowTitle(WinError.title_text)

        self.central_layout.setContentsMargins(7, 7, 7, 12)
        self.central_layout.setSpacing(0)

        h_wid = QWidget()
        self.central_layout.addWidget(h_wid)

        h_lay = QHBoxLayout(h_wid)
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.setSpacing(10)

        warn = QSvgWidget()
        warn.load(self.icon_path)
        warn.setFixedSize(self.icon_size, self.icon_size)
        h_lay.addWidget(warn)

        test_two = QLabel(WinError.descr_text)
        test_two.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        h_lay.addWidget(test_two)

        ok_btn = BtnSmall(WinError.ok_text)
        ok_btn.clicked.connect(self.deleteLater)
        ok_btn.setFixedWidth(90)
        self.central_layout.addWidget(ok_btn, alignment=Qt.AlignmentFlag.AlignCenter)

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


class WinCopyFiles(WinProgressbar):
    finished_ = pyqtSignal(list)
    preparing_text = "Подготовка"
    progressbar_width = 300
    icon_size = 50
    copy_timer_ms = 100

    def __init__(self):
        if ClipboardItemGlob.is_cut:
            title_text = "Перемещаю файлы"
        else:
            title_text = "Копирую файлы"

        super().__init__(title_text)

        self.dst_urls: list[str] = []
        self.copy_item: CopyTaskItem | None = None
        self.replace_win: WinReplaceFiles | None = None
        self.stopping = False

        src_txt = self.limit_string(os.path.basename(ClipboardItemGlob.src_dir))
        dest_txt = self.limit_string(os.path.basename(ClipboardItemGlob.dst_dir))
        self.above_label.setText(f'Из "{src_txt}" в "{dest_txt}"')
        self.below_label.setText(self.preparing_text)
        self.progressbar.setMaximum(100)
        self.cancel_btn.clicked.connect(self.stop_task)
        self.cancel_btn.clicked.connect(self.deleteLater)
        self.adjustSize()

        self.copy_item = CopyTaskItem(
            dst_dir=ClipboardItemGlob.dst_dir,
            src_urls=ClipboardItemGlob.src_urls,
            current_percent=0,
            copied_bytes=0,
            total_bytes=0,
            current_file_count=0,
            total_file_count=0,
            dst_urls=[],
            msg="none",
            is_cut=ClipboardItemGlob.is_cut,
        )

        self.copy_task = CopyTaskWorker(
            target=CopyTask.start,
            args=(self.copy_item,),
        )

        self.copy_timer = QTimer(self)
        self.copy_timer.setSingleShot(True)
        self.copy_timer.timeout.connect(self.poll_task)

        self.copy_task.start()
        self.copy_timer.start(self.copy_timer_ms)

    def poll_task(self):
        if self.stopping:
            return

        while True:
            try:
                copy_item: CopyTaskItem = self.copy_task.process_queue.get_nowait()
            except Empty:
                break

            self.copy_item = copy_item

            if copy_item.dst_urls:
                self.dst_urls = list(copy_item.dst_urls)

            if copy_item.msg == "error":
                self.show_error(copy_item.error_traceback)
                return

            if copy_item.msg == "need_replace":
                self.show_replace_window()
                return

            if copy_item.msg == "finished":
                self.finish_task()
                return

            self.update_progress(copy_item)

        if not self.copy_task.is_alive():
            self.finish_task()
            return

        self.copy_timer.start(self.copy_timer_ms)

    def update_progress(self, copy_item: CopyTaskItem):
        self.progressbar.setValue(copy_item.current_percent)
        self.below_label.setText(
            f"{self.windowTitle()} {copy_item.current_file_count} из {copy_item.total_file_count}"
        )

    def show_replace_window(self):
        if self.stopping:
            return

        self.replace_win = WinReplaceFiles()
        self.replace_win.center(self)
        self.replace_win.replace_one_press.connect(self.replace_one)
        self.replace_win.replace_all_press.connect(self.replace_all)
        self.replace_win.stop_pressed.connect(self.cancel_from_replace)
        self.replace_win.show()

    def replace_one(self):
        if self.stopping:
            return
        self.close_replace_window()
        self.copy_task.replace_one()
        self.copy_timer.start(self.copy_timer_ms)

    def replace_all(self):
        if self.stopping:
            return
        self.close_replace_window()
        self.copy_task.replace_all()
        self.copy_timer.start(self.copy_timer_ms)

    def cancel_from_replace(self):
        self.stop_task()
        self.deleteLater()

    def close_replace_window(self):
        if self.replace_win is None:
            return
        window = self.replace_win
        self.replace_win = None
        # WinReplaceFiles игнорирует closeEvent, поэтому только deleteLater
        window.deleteLater()

    def show_error(self, traceback_text: str):
        if self.stopping:
            return

        self.close_replace_window()
        print(traceback_text)

        self.error_win = WinError()
        self.error_win.center(self.window())
        self.error_win.show()

        self.stop_task()
        self.deleteLater()

    def finish_task(self):
        if self.stopping:
            return

        total = self.copy_item.total_file_count if self.copy_item else 0
        self.progressbar.setValue(100)
        self.below_label.setText(f"{self.windowTitle()} {total} из {total}")

        self.finished_.emit(self.dst_urls)

        self.stop_task()
        self.deleteLater()

    def stop_task(self):
        if self.stopping:
            return

        self.stopping = True
        self.copy_timer.stop()
        self.close_replace_window()

        if self.copy_task.is_alive():
            self.copy_task.cancel()

        self.copy_task.terminate_join()

    def limit_string(self, text: str, limit: int = 30):
        if len(text) > limit:
            return text[:limit] + "..."
        return text

    def closeEvent(self, a0):
        self.stop_task()
        ClipboardItemGlob.reset()
        return super().closeEvent(a0)

    def deleteLater(self):
        ClipboardItemGlob.reset()
        super().deleteLater()