import os
import shutil
from dataclasses import dataclass
from multiprocessing import Process, Queue
from pathlib import Path
from time import sleep

import numpy as np
import sqlalchemy
from PIL import Image
from PyQt5.QtCore import QTimer
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers.polling import PollingObserver as Observer

from cfg import Static
from system.database import CacheTable, Dbase
from system.items import (CopyItem, DataItem, ImgLoaderItem, JpgConvertItem,
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


@dataclass(slots=True)
class ImgLoaderHelper:
    task: ProcessWorker
    timer: QTimer


class ImgLoader:

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

        for data, thumb_path in db_items_dict.items():
            if data in finder_items_dict:
                data_item = finder_items_dict[data]
                # print("yes", data_item.filename)
                data_item._img_array = Utils.read_thumb(thumb_path)
                if data_item._img_array is None:
                    new_items.append(data_item)
                else:
                    queue.put(data_item)

        for (filename, mod, size), data_item in finder_items_dict.items():
            if (filename, mod, size) not in db_items_dict:
                # print("new", data_item.filename)
                new_items.append(data_item)

        if new_items:
            ImgLoader.process_items(img_item, new_items)

    @staticmethod
    def process_items(img_item: ImgLoaderItem, data_items: list[DataItem]):
        step = 10
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
    

class ReadImg:
    @staticmethod
    def start(src: str, desaturate: bool, queue: Queue):
        img_array = ImgUtils.read_img(src)
        queue.put((src, img_array))


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
            resol= f"{w}x{h}"
        except Exception as e:
            print("multiprocess > ImgRes psd error", e)
            resol = ImgRes.undef_text
        return resol

    @staticmethod
    def read(path: str):
        img_ = ImgUtils.read_img(path)
        if img_ is not None and len(img_.shape) > 1:
            h, w = img_.shape[0], img_.shape[1]
            resol= f"{w}x{h}"
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
            folders = set(),
            files = set()
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


class CopyWorker(BaseProcessWorker):
    def __init__(self, target, args):
        self.queue = Queue()
        self.gui_queue = Queue()
        super().__init__(target, (*args, self.queue, self.gui_queue))


class CopyTask:
    @staticmethod
    def start(copy_item: CopyItem, queue: Queue, gui_queue: Queue):
        if copy_item.src_dir != copy_item.dst_dir:
            src_dst_urls = CopyTask.get_another_dir_urls(copy_item)
        else:
            src_dst_urls = CopyTask.get_same_dir_urls(copy_item)

        copy_item.dst_urls = [dst for src, dst in src_dst_urls]

        total_size = 0
        for src, dest in src_dst_urls:
            total_size += os.path.getsize(src)

        copy_item.total_size = total_size // 1024
        copy_item.total_count = len(src_dst_urls)
        replace_all = False

        for count, (src, dest) in enumerate(src_dst_urls, start=1):

            if src.is_dir():
                continue

            if not replace_all and dest.exists() and src.name == dest.name:
                copy_item.msg = "need_replace"
                queue.put(copy_item)
                while True:
                    sleep(1)
                    if not gui_queue.empty():
                        new_copy_item: CopyItem = gui_queue.get()
                        if new_copy_item.msg == "replace_one":
                            break
                        elif new_copy_item.msg == "replace_all":
                            replace_all = True
                            break

            os.makedirs(dest.parent, exist_ok=True)
            copy_item.current_count = count
            copy_item.msg = ""
            try:
                if os.path.exists(dest) and dest.is_file():
                    os.remove(dest)
                CopyTask.copy_file_with_progress(queue, copy_item, src, dest)
            except Exception as e:
                print("CopyTask copy error", e)
                copy_item.msg = "error"
                queue.put(copy_item)
                return
            if copy_item.is_cut:
                os.remove(src)
                "удаляем файлы чтобы очистить директории"

        if copy_item.is_cut:
            for src, dst in src_dst_urls:
                if src.is_dir() and src.exists():
                    try:
                        shutil.rmtree(src)
                    except Exception as e:
                        print("copy task error dir remove", e)
        
        copy_item.msg = "finished"
        queue.put(copy_item)

    @staticmethod
    def get_another_dir_urls(copy_item: CopyItem):
        src_dst_urls: list[tuple[Path, Path]] = []
        src_dir = Path(copy_item.src_dir)
        dst_dir = Path(copy_item.dst_dir)
        for url in copy_item.src_urls:
            url = Path(url)
            if url.is_dir():
                # мы добавляем директорию в список копирования
                # чтобы потом можно было удалить ее при вырезании
                src_dst_urls.append((url, url))
                for filepath in url.rglob("*"):
                    if filepath.is_file():
                        rel_path = filepath.relative_to(src_dir)
                        new_path = dst_dir.joinpath(rel_path)
                        src_dst_urls.append((filepath, new_path))
            else:
                new_path = dst_dir.joinpath(url.name)
                src_dst_urls.append((url, new_path))
        return src_dst_urls
    
    @staticmethod
    def get_same_dir_urls(copy_item: CopyItem, copy_name: str = ""):
        src_dst_urls: list[tuple[Path, Path]] = []
        dst_dir = Path(copy_item.dst_dir)
        for url in copy_item.src_urls:
            url = Path(url)
            url_with_copy = dst_dir.joinpath(url.name)
            counter = 2
            while url_with_copy.exists():
                name, ext = os.path.splitext(url.name)
                new_name = f"{name} {copy_name} {counter}{ext}"
                url_with_copy = dst_dir.joinpath(new_name)
                counter += 1
            if url.is_file():
                src_dst_urls.append((url, url_with_copy))
            else:
                for filepath in url.rglob("*"):
                    if filepath.is_file():
                        rel_path = filepath.relative_to(url)
                        new_url = url_with_copy.joinpath(rel_path)
                        src_dst_urls.append((filepath, new_url))
        return src_dst_urls
    
    @staticmethod
    def copy_file_with_progress(queue: Queue, copy_item: CopyItem, src: Path, dest: Path):
        block = 4 * 1024 * 1024  # 4 MB
        with open(src, "rb") as fsrc, open(dest, "wb") as fdst:
            while True:
                buf = fsrc.read(block)
                if not buf:
                    break
                fdst.write(buf)
                copy_item.current_size += len(buf) // 1024
                queue.put(copy_item)
        try:
            shutil.copystat(src, dest, follow_symlinks=True)
        except OSError:
            print("copy stat error CopyTask")


class SearchTask:
    sleep_s = 0.1

    @staticmethod
    def start(search_item: SearchItem, queue: Queue):
        search_item.engine = Dbase.create_engine()
        search_item.queue = queue
        search_item.missed_files = search_item.search_list.copy()
        SearchTask.scandir_recursive(search_item)
        search_item.queue.put(search_item.missed_files)

        # fs_id и rel_parent мы можем получать когда делаем
        # scan current dir, потому что знаем наверняка, что сейчас
        # сканится одна директория
        # в рамках этого:
        # загрузить кешированную миниатюру:
        # ищем строку в БД по fs_id rel_parent и сравниваем размер и дату
        # если есть - загружаем, если нет, отправляем в список на инсерт
        # сразу со всеми данными включая array

        # когда мы сканим конкретную диру, мы сразу забираем из БД
        # одним SELECT все что относится к ней, чтобы сравнивать и
        # открываеть подключения для каждого select

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
