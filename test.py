class URunnable(QRunnable):
    def __init__(self):
        """
        Переопределите метод task().
        Не переопределяйте run().
        """
        super().__init__()
        self.should_run__ = True
        self.finished__ = False

    def is_should_run(self):
        return self.should_run__
    
    def set_should_run(self, value: bool):
        self.should_run__ = value

    def set_finished(self, value: bool):
        self.finished__ = value

    def is_finished(self):
        return self.finished__
    
    def run(self):
        try:
            self.task()
        finally:
            self.set_finished(True)
            if self in UThreadPool.tasks:
                QTimer.singleShot(5000, lambda: self.task_fin())

    def task(self):
        raise NotImplementedError("Переопредели метод task() в подклассе.")
    
    def task_fin(self):
        UThreadPool.tasks.remove(self)
        gc.collect()


class UThreadPool:
    pool: QThreadPool = None
    tasks: list[URunnable] = []

    @classmethod
    def init(cls):
        cls.pool = QThreadPool.globalInstance()
        # cls.pool.setMaxThreadCount(5)

    @classmethod
    def start(cls, runnable: QRunnable):
        # cls.tasks.append(runnable)
        cls.pool.start(runnable)


class DirWatcher(URunnable):

    class Sigs(QObject):
        changed = pyqtSignal(object)

    def __init__(self, path: str):
        super().__init__()
        self.path = path
        self.sigs = DirWatcher.Sigs()

    def on_dirs_changed(self, e: FileSystemEvent):
        if e.src_path != self.path:
            self.sigs.changed.emit(e)

    def wait_dir(self):
        while self.is_should_run():
            if os.path.exists(self.path):
                return
            QThread.msleep(1000)

    def task(self):
        try:
            self._task()
        except Exception as e:
            print("tasks, DirWatcher error", e)

    def _task(self):
        self.wait_dir()
        if not self.is_should_run():
            return

        observer = Observer()
        handler = _DirChangedHandler(self.on_dirs_changed)
        observer.schedule(handler, self.path, recursive=False)
        observer.start()

        try:
            while self.is_should_run():
                QThread.msleep(1000)
                if not os.path.exists(self.path):
                    observer.stop()
                    observer.join()
                    self.wait_dir()
                    if not self.is_should_run():
                        return
                    observer = Observer()
                    observer.schedule(handler, self.path, recursive=False)
                    observer.start()
        finally:
            observer.stop()
            observer.join()