import os
import traceback
from dataclasses import dataclass
from enum import Enum, auto
from multiprocessing import Process, Queue, shared_memory
from pathlib import Path
from queue import Empty
from time import sleep
from typing import Literal

import numpy as np
import sqlalchemy
from PIL import Image
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers.polling import PollingObserver as Observer

from cfg import Static
from system.database import CacheTable, Dbase
from system.items import (DataItem, ImgLoaderItem, JpgConvertItem,
                          MainWinItem, MultipleInfoItem, SearchItem)
from system.shared_utils import ImgUtils, SharedUtils
from system.tasks import Utils


class BaseProcessWorker:
    _registry = []

    def __init__(self, target: callable, args: tuple):
        super().__init__()
        self.process = Process(target=target, args=(*args, ))
        self._queues: list[Queue] = [a for a in args if hasattr(a, 'put')]
        BaseProcessWorker._registry.append(self)

    def start(self):
        self.process.start()

    def is_alive(self):
        return self.process.is_alive()

    def terminate_join(self):
        """
        Корректно terminate с join
        Завершает все очереди Queue
        """
        self.process.terminate()
        self.process.join(timeout=0.2)

        for q in self._queues:
            q.close()
            q.cancel_join_thread()

        if self.process.is_alive():
            self.process.kill()

        if self in BaseProcessWorker._registry:
            BaseProcessWorker._registry.remove(self)

    @staticmethod
    def stop_all():
        for worker in BaseProcessWorker._registry.copy():
            worker: BaseProcessWorker
            worker.terminate_join()


class ProcessWorker(BaseProcessWorker):
    """
        Передает в BaseProcessWorker args + self.proc (Queue)
    """
    def __init__(self, target: callable, args: tuple):
        self.queue = Queue()
        super().__init__(target, (*args, self.queue))


class ImgLoader:
    # Баланс между нагрузкой на диск и риском потери данных при сбое.
    # Большое значение ускоряет работу,но увеличивает объем потенциально
    # утерянных данных.
    chunk_size = 5

    @staticmethod
    def start(
        data_items: list[DataItem],
        main_win_item: MainWinItem,
        queue: Queue
    ):

        if not os.path.exists(main_win_item.abs_current_dir):
            return

        engine = Dbase.create_engine()
        img_item = ImgLoaderItem(
            engine=engine,
            queue=queue,
            fs_id=main_win_item.fs_id,
            rel_parent=main_win_item.rel_parent
        )

        data_items = sorted(data_items, key=lambda x: x.size)

        res = ImgLoader._get_records(img_item)
        db_items_dict = {
            (filename, mod, size): thumb_path
            for filename, mod, size, thumb_path in res
        }

        finder_items_dict = {
            (data_item.filename, data_item.mod, data_item.size): data_item
            for data_item in data_items
        }

        new_items: list[DataItem] = []
        icon_path = os.path.join(
            Static.internal_images_dir,
            "broken_thumb.jpg"
        )
        broken_thumb = Utils.read_thumb(icon_path)

        for data, thumb_path in db_items_dict.items():
            if data in finder_items_dict:
                data_item = finder_items_dict[data]
                data_item._img_array = Utils.read_thumb(thumb_path)
                if data_item._img_array is None:
                    new_items.append(data_item)
                # битые изображения пытаться загрузить заново
                elif np.array_equal(data_item._img_array, broken_thumb):
                    new_items.append(data_item)
                else:
                    queue.put(data_item)

        for (filename, mod, size), data_item in finder_items_dict.items():
            if (filename, mod, size) not in db_items_dict:
                new_items.append(data_item)

        new_items = sorted(new_items, key=lambda x: x.size)
        if new_items:
            ImgLoader.process_new_items(img_item, new_items)

    @staticmethod
    def process_new_items(img_item: ImgLoaderItem, data_items: list[DataItem]):
        step = 5
        chunks = [
            data_items[i:i+step]
            for i in range(0, len(data_items), step)
        ]
        for chunk in chunks:
            for data_item in chunk:
                _img = ImgUtils.read_img(data_item.abs_path)
                data_item._thumb_path = Utils.create_thumb_path(
                    filename=data_item.filename,
                    mod=data_item.mod,
                    rel_parent=img_item.rel_parent,
                    fs_id=img_item.fs_id
                )
                data_item._img_array = ImgUtils.resize(
                    image=_img,
                    size=Static.max_thumb_size
                )
                Utils.write_thumb(
                    thumb_path=data_item._thumb_path,
                    thumb_array=data_item._img_array
                )
                img_item.queue.put(data_item)
            ImgLoader._insert_records(
                img_item=img_item,
                data_items=chunk
            )

    @staticmethod
    def _insert_records(img_item: ImgLoaderItem, data_items: list[DataItem]):
        if not data_items:
            return
        values: list[dict] = []
        for i in data_items:
            values.append({
                CacheTable.filename.name: i.filename,
                CacheTable.rel_parent.name: img_item.rel_parent,
                CacheTable.fs_id.name: img_item.fs_id,
                CacheTable.thumb_path.name: i._thumb_path,
                CacheTable.size.name: i.size,
                CacheTable.mod.name: i.mod
            })
        stmt = (
            sqlalchemy.insert(CacheTable.table)
        )
        with img_item.engine.begin() as conn:
            conn.execute(stmt, values)

    @staticmethod
    def _get_records(img_item: ImgLoaderItem):
        clmns = (
            CacheTable.filename,
            CacheTable.mod,
            CacheTable.size,
            CacheTable.thumb_path
        )
        stmt = (
            sqlalchemy.select(*clmns)
            .where(CacheTable.fs_id==img_item.fs_id)
            .where(CacheTable.rel_parent==img_item.rel_parent)
        )
        with img_item.engine.connect() as conn:
            return conn.execute(stmt)


@dataclass(slots=True)
class ReadImgItem:
    src: str
    shm_name: str
    shape: tuple[int, ...]
    dtype: str


class ReadImg:
    @staticmethod
    def start(src: str, desaturate: bool, queue: Queue):
        img_array = ImgUtils.read_img(src)

        shm = shared_memory.SharedMemory(create=True, size=img_array.nbytes)
        buffer = np.ndarray(img_array.shape, dtype=img_array.dtype, buffer=shm.buf)
        buffer[:] = img_array
        item = ReadImgItem(
            src=src,
            shm_name=shm.name,
            shape=img_array.shape,
            dtype=img_array.dtype.str
        )
        queue.put(item)
        shm.close()


class _DirChangedHandler(FileSystemEventHandler):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def on_any_event(self, event: FileSystemEvent):
        dest_path = getattr(event, "dest_path", "")
        stmt = any((
            event.src_path.lower().endswith(ImgUtils.ext_all),
            dest_path.lower().endswith(ImgUtils.ext_all),
            event.is_directory
        ))
        if stmt:
            self.callback(event)


class WatchdogTask:
    @staticmethod
    def start(path: str, recursive: bool, queue: Queue):
        if not path or not os.path.exists(path):
            return

        observer = Observer()
        handler = _DirChangedHandler(lambda e: queue.put(e))
        observer.schedule(handler, path, recursive=recursive)
        observer.start()
        try:
            while True:
                sleep(1)
                if not os.path.exists(path):
                    break
        finally:
            observer.stop()
            observer.join()


class JpgConverter:
    @staticmethod
    def start(jpg_item: JpgConvertItem, queue: Queue):
        jpg_item.urls = [
            i
            for i in jpg_item.urls
            if i.endswith(ImgUtils.ext_all)
        ]
        jpg_item.urls.sort(key=lambda p: os.path.getsize(p))

        filename = ""
        new_urls: list[str] = []

        for count, url in enumerate(jpg_item.urls, start=1):
            save_path = JpgConverter._save_jpg(url)
            if save_path:
                new_urls.append(save_path)
                filename = os.path.basename(url)
                jpg_item.current_count = count
                jpg_item.current_filename = filename
                jpg_item.msg = ""
                queue.put(jpg_item)

        jpg_item.msg = "finished"
        queue.put(jpg_item)

    @staticmethod
    def _save_jpg(path: str) -> None:
        try:
            img_array = ImgUtils.read_img(path)
            image = Image.fromarray(img_array.astype(np.uint8))
            save_path = os.path.splitext(path)[0] + ".jpg"
            profile = ImgUtils.read_icc(path)
            if profile:
                image.save(save_path, quality=100, icc_profile=profile)
            else:
                image.save(save_path, quality=100)
            return save_path
        except Exception:
            Utils.print_error()
            return None


class ImgRes:
    undef_text = "Неизвестно"

    @staticmethod
    def psd_read(path: str):
        try:
            w, h = ImgUtils.get_psd_size(path)
            resol = f"{w}x{h}"
        except Exception as e:
            print("multiprocess > ImgRes psd error", e)
            resol = ImgRes.undef_text
        return resol

    @staticmethod
    def read(path: str):
        img_ = ImgUtils.read_img(path)
        if img_ is not None and len(img_.shape) > 1:
            h, w = img_.shape[0], img_.shape[1]
            resol = f"{w}x{h}"
        else:
            resol = ImgRes.undef_text
        return resol

    @staticmethod
    def start(path: str, queue: Queue):
        """
        Возвращает str "ширина изображения x высота изображения
        """
        if path.endswith(ImgUtils.ext_psd):
            resol = ImgRes.psd_read(path)
        else:
            resol = ImgRes.read(path)
        queue.put(resol)


class MultipleInfo:
    err = " Произошла ошибка"

    @staticmethod
    def start(data_items: list[DataItem], queue: Queue):
        info_item = MultipleInfoItem(
            total_size=0,
            total_files=0,
            total_folders=0,
            folders=set(),
            files=set()
        )

        try:
            MultipleInfo._task(data_items, info_item)
            info_item.total_size = SharedUtils.get_f_size(info_item.total_size)
            info_item.total_files = len(list(info_item.files))
            info_item.total_files = format(info_item.total_files, ",").replace(",", " ")
            info_item.total_folders = len(list(info_item.folders))
            info_item.total_folders = format(info_item.total_folders, ",").replace(",", " ")
            queue.put(info_item)

        except Exception as e:
            print("tasks, MultipleInfoFiles error", e)
            info_item.total_size = MultipleInfo.err
            info_item.total_files = MultipleInfo.err
            info_item.total_folders = MultipleInfo.err
            queue.put(info_item)

    @staticmethod
    def _task(items: list[dict], info_item: MultipleInfoItem):
        for i in items:
            if i["type_"] == Static.folder_type:
                MultipleInfo.get_folder_size(i, info_item)
                info_item.folders.add(i["src"])
            else:
                info_item.total_size += i["size"]
                info_item.files.add(i["src"])

    @staticmethod
    def get_folder_size(item: dict, info_item: MultipleInfoItem):
        stack = [item["src"]]
        while stack:
            current_dir = stack.pop()
            try:
                os.listdir(current_dir)
            except Exception as e:
                print("tasks, MultipleItemsInfo error", e)
                break
            for entry in os.scandir(current_dir):
                if entry.name.startswith(Static.hidden_symbols):
                    continue
                if entry.is_dir():
                    info_item.folders.add(item["src"])
                    stack.append(entry.path)
                else:
                    info_item.total_size += entry.stat().st_size
                    info_item.files.add(entry.path)


@dataclass(slots=True)
class CopyTaskItem:
    dst_dir: str
    src_urls: list[str]
    current_percent: int
    copied_bytes: int
    total_bytes: int
    current_file_count: int
    total_file_count: int
    dst_urls: list[str]
    msg: Literal["none", "error", "need_replace", "finished"]
    error_traceback: str = ""
    is_cut: bool = False


class CopyCommand(Enum):
    REPLACE_ONE = auto()
    REPLACE_ALL = auto()
    SKIP = auto()
    CANCEL = auto()
    KEEP_BOTH = auto()
    KEEP_ALL = auto()


@dataclass(slots=True)
class CopyPlanItem:
    top_dest: Path
    src_dirs: list[Path]
    dest_dirs: list[Path]
    files: list[tuple[Path, Path]]


class CopyTaskWorker(BaseProcessWorker):
    def __init__(self, target, args):
        self.process_queue = Queue()
        self.gui_queue = Queue()
        super().__init__(target, (*args, self.process_queue, self.gui_queue))

    def replace_one(self):
        self.gui_queue.put(CopyCommand.REPLACE_ONE)

    def replace_all(self):
        self.gui_queue.put(CopyCommand.REPLACE_ALL)

    def skip(self):
        self.gui_queue.put(CopyCommand.SKIP)

    def cancel(self):
        self.gui_queue.put(CopyCommand.CANCEL)

    def keep_both(self):
        self.gui_queue.put(CopyCommand.KEEP_BOTH)

    def keep_all(self):
        self.gui_queue.put(CopyCommand.KEEP_ALL)


# Совместимость: если где-то импортируется старое имя
CopyWorker = CopyTaskWorker


class CopyTask:
    @staticmethod
    def start(copy_item: CopyTaskItem, process_queue: Queue, gui_queue: Queue):
        try:
            plan = CopyTask.build_plan(copy_item)

            copy_item.dst_urls = []
            copy_item.total_file_count = sum(len(p.files) for p in plan)
            copy_item.total_bytes = sum(
                src.stat().st_size for p in plan for src, _ in p.files
            )

            replace_all = False
            keep_all = False
            count = 0
            moved: list[Path] = []

            for entry in plan:
                for dest_dir in entry.dest_dirs:
                    dest_dir.mkdir(parents=True, exist_ok=True)

                copied_any = False

                for src, dest in entry.files:
                    count += 1
                    copy_item.current_file_count = count

                    if dest.exists():
                        if keep_all:
                            dest = CopyTask.set_count_name(dest)

                        elif not replace_all:
                            copy_item.msg = "need_replace"
                            process_queue.put(copy_item)

                            command = CopyTask.wait_command(gui_queue)

                            if command == CopyCommand.CANCEL:
                                return
                            if command == CopyCommand.SKIP:
                                continue
                            if command == CopyCommand.REPLACE_ALL:
                                replace_all = True
                            elif command == CopyCommand.KEEP_ALL:
                                keep_all = True
                                dest = CopyTask.set_count_name(dest)
                            elif command == CopyCommand.KEEP_BOTH:
                                dest = CopyTask.set_count_name(dest)
                            elif command != CopyCommand.REPLACE_ONE:
                                return

                    copy_item.msg = "none"
                    copy_item.error_traceback = ""

                    result = CopyTask.copy_file_with_progress(
                        process_queue, gui_queue, copy_item, src, dest
                    )
                    if result == CopyCommand.CANCEL:
                        return

                    copied_any = True
                    moved.append(src)

                if copied_any:
                    copy_item.dst_urls.append(str(entry.top_dest))

            if copy_item.is_cut:
                CopyTask.remove_sources(plan, moved)

            copy_item.current_percent = 100
            copy_item.msg = "finished"
            process_queue.put(copy_item)

        except Exception:
            CopyTask.report_error(copy_item, process_queue)

    @staticmethod
    def build_plan(copy_item: CopyTaskItem) -> list[CopyPlanItem]:
        dst_dir = Path(copy_item.dst_dir)
        plan: list[CopyPlanItem] = []

        for url in copy_item.src_urls:
            src = Path(url)
            same_dir = src.parent.resolve() == dst_dir.resolve()

            # Перемещение в ту же папку ничего не меняет
            if copy_item.is_cut and same_dir:
                continue

            top_dest = dst_dir / src.name
            if same_dir:
                top_dest = CopyTask.set_count_name(top_dest)

            if src.is_dir():
                all_paths = list(src.rglob("*"))
                src_dirs = [src] + [p for p in all_paths if p.is_dir()]
                dest_dirs = [top_dest / p.relative_to(src) for p in src_dirs]
                files = [
                    (p, top_dest / p.relative_to(src))
                    for p in all_paths if p.is_file()
                ]
            else:
                src_dirs, dest_dirs = [], []
                files = [(src, top_dest)]

            plan.append(CopyPlanItem(top_dest, src_dirs, dest_dirs, files))

        return plan

    @staticmethod
    def remove_sources(plan: list[CopyPlanItem], moved: list[Path]):
        for src in moved:
            try:
                src.unlink()
            except OSError as e:
                print("CopyTask cannot remove source", src, e)

        # Удаляем пустые папки источника: сначала вложенные, потом корневые
        for entry in plan:
            for src_dir in sorted(
                entry.src_dirs, key=lambda p: len(p.parts), reverse=True
            ):
                try:
                    src_dir.rmdir()
                except OSError:
                    pass

    @staticmethod
    def report_error(copy_item: CopyTaskItem, process_queue: Queue):
        copy_item.msg = "error"
        copy_item.error_traceback = traceback.format_exc()
        process_queue.put(copy_item)

    @staticmethod
    def wait_command(gui_queue: Queue):
        while True:
            try:
                return gui_queue.get(timeout=0.1)
            except Empty:
                continue

    @staticmethod
    def check_command(gui_queue: Queue):
        try:
            while True:
                command = gui_queue.get_nowait()
                if command == CopyCommand.CANCEL:
                    return command
        except Empty:
            return None

    @staticmethod
    def copy_file_with_progress(
        process_queue: Queue,
        gui_queue: Queue,
        copy_item: CopyTaskItem,
        src: Path,
        dest: Path,
    ):
        block = 4 * 1024 * 1024
        backup = None

        try:
            if dest.exists():
                backup = CopyTask.set_count_name(dest)
                dest.rename(backup)

            with open(src, "rb") as fsrc, open(dest, "wb") as fdst:
                while True:
                    command = CopyTask.check_command(gui_queue)
                    if command == CopyCommand.CANCEL:
                        raise InterruptedError("Копирование отменено")

                    buf = fsrc.read(block)
                    if not buf:
                        break

                    fdst.write(buf)
                    copy_item.copied_bytes += len(buf)

                    if copy_item.total_bytes:
                        percent = (
                            copy_item.copied_bytes * 100
                        ) // copy_item.total_bytes

                        if percent > copy_item.current_percent:
                            copy_item.current_percent = percent
                            process_queue.put(copy_item)

                fdst.flush()
                os.fsync(fdst.fileno())

            stat = src.stat()
            os.utime(dest, ns=(stat.st_atime_ns, stat.st_mtime_ns))

            if backup is not None:
                backup.unlink()
                backup = None

            return None

        except Exception:
            error = traceback.format_exc()

            try:
                if dest.exists():
                    dest.unlink()
            except OSError:
                error += (
                    "\nОшибка удаления частичного файла:\n"
                    + traceback.format_exc()
                )

            if backup is not None and backup.exists():
                try:
                    backup.rename(dest)
                except OSError:
                    error += (
                        "\nОшибка восстановления резервной копии:\n"
                        + traceback.format_exc()
                    )

            copy_item.msg = "error"
            copy_item.error_traceback = error
            process_queue.put(copy_item)

            return CopyCommand.CANCEL

    @staticmethod
    def set_count_name(path: Path) -> Path:
        counter = 2
        filename, ext = os.path.splitext(path.name)
        parent = path.parent

        while path.exists():
            path = parent / f"{filename} ({counter}){ext}"
            counter += 1

        return path


class SearchTask:
    sleep_s = 0.1

    @staticmethod
    def start(search_item: SearchItem, queue: Queue):
        search_item.engine = Dbase.create_engine()
        search_item.queue = queue
        search_item.missed_files = search_item.search_list.copy()
        SearchTask.scandir_recursive(search_item)
        search_item.queue.put(search_item.missed_files)

    # базовый метод обработки os.DirEntry
    @staticmethod
    def process_entry(entry: os.DirEntry[str], search_item: SearchItem):
        for low in search_item.search_list:
            if low in entry.name.lower():
                if low in search_item.missed_files:
                    search_item.missed_files.pop(low)
                return True
        return False

    @staticmethod
    def scandir_recursive(search_item: SearchItem):
        dirs_list = [search_item.root_dir, ]
        while dirs_list:
            current_dir = dirs_list.pop()
            if not os.path.exists(current_dir):
                continue
            try:
                # Сканируем текущий каталог и добавляем новые пути в стек
                SearchTask.scan_single_dir(current_dir, dirs_list, search_item)
            except OSError as e:
                Utils.print_error()
                continue
            except Exception as e:
                Utils.print_error()
                continue

    @staticmethod
    def scan_single_dir(current_dir: str, dir_list: list, search_item: SearchItem):
        fs_id = Utils.get_fs_id(current_dir)
        rel_parent = Utils.get_rel_parent(current_dir)
        search_item.fs_id = fs_id
        search_item.rel_parent = rel_parent

        with search_item.engine.connect() as conn:
            clmns = (
                CacheTable.thumb_path,
                CacheTable.filename,
                CacheTable.size,
                CacheTable.mod
            )
            stmt = (
                sqlalchemy.select(*clmns)
                .where(CacheTable.fs_id==fs_id)
                .where(CacheTable.rel_parent==rel_parent)
            )
            search_item.db_items = {
                (filename, size, mod): thumb_path
                for thumb_path, filename, size, mod in conn.execute(stmt)
            }

        step = 5
        for x, entry in enumerate(os.scandir(current_dir), start=1):
            if entry.name.startswith(Static.hidden_symbols):
                continue
            if entry.is_dir():
                dir_list.append(entry.path)
            if SearchTask.process_entry(entry, search_item):
                SearchTask.process_data_item(entry, search_item)
            if x == step:
                SearchTask.insert_records(search_item, search_item.new_items)
                search_item.new_items.clear()
        SearchTask.insert_records(search_item, search_item.new_items)
        search_item.new_items.clear()

    @staticmethod
    def process_data_item(entry: os.DirEntry[str], search_item: SearchItem):
        data_item = DataItem(entry.path)
        data_item.set_properties()
        if entry.is_dir():
            search_item.queue.put(data_item)
        elif entry.name.endswith(ImgUtils.ext_all):
            props = data_item.filename, data_item.size, data_item.mod
            if props in search_item.db_items:
                path = search_item.db_items[props]
                data_item._img_array = Utils.read_thumb(path)
            else:
                img_array = ImgUtils.read_img(data_item.abs_path)
                data_item._thumb_path = Utils.create_thumb_path(
                    filename=data_item.filename,
                    mod=data_item.mod,
                    rel_parent=search_item.rel_parent,
                    fs_id=search_item.fs_id
                )
                data_item._img_array = ImgUtils.resize(
                    image=img_array,
                    size=Static.max_thumb_size
                )
                Utils.write_thumb(data_item._thumb_path, data_item._img_array)
                search_item.new_items.append(data_item)
            search_item.queue.put(data_item)

    def insert_records(search_item: SearchItem, data_items: list[DataItem]):
        if not data_items:
            return
        values = []
        for i in data_items:
            values.append({
                CacheTable.filename.name: i.filename,
                CacheTable.rel_parent.name: search_item.rel_parent,
                CacheTable.fs_id.name: search_item.fs_id,
                CacheTable.thumb_path.name: i._thumb_path,
                CacheTable.size.name: i.size,
                CacheTable.mod.name: i.mod
            })
        with search_item.engine.begin() as conn:
            stmt = sqlalchemy.insert(CacheTable.table)
            conn.execute(stmt, values)