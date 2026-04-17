import os
import shutil
from multiprocessing import Process, Queue
from pathlib import Path
from time import sleep

import numpy as np
import sqlalchemy
from PIL import Image
from watchdog.events import FileSystemEventHandler
from watchdog.observers.polling import PollingObserver as Observer

from cfg import Static
from system.database import CacheTable, Dbase
from system.items import (CopyItem, DataItem, ImgLoaderItem, JpgConvertItem,
                          MainWinItem, MultipleInfoItem, PathFixerItem,
                          SearchItem)
from system.shared_utils import ImgUtils, PathFinder, SharedUtils
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
        self.process_queue = Queue()
        super().__init__(target, (*args, self.process_queue))


class ImgLoader:

    @staticmethod
    def start(data_items: list[DataItem], main_win_item: MainWinItem, queue: Queue):
        if not os.path.exists(main_win_item.abs_current_dir):
            return
        fs_id = Utils.get_fs_id(main_win_item.abs_current_dir)
        if main_win_item.abs_current_dir.startswith("/Users"):
            rel_parent = main_win_item.abs_current_dir
        else:
            splited = main_win_item.abs_current_dir.strip(os.sep).split(os.sep)
            rel_parent = os.sep + os.sep.join(splited[2:])
        data_items = sorted(data_items, key=lambda x: x.size)

        with Dbase.create_engine().begin() as conn:
            img_item = ImgLoaderItem(conn, fs_id, rel_parent)
            res = ImgLoader._get_records(img_item)
            db_items_dict = {
                (filename, mod, size): thumb_path
                for thumb_path, filename, mod, size in res
            }
            data_items_dict = {
                (i.filename, i.mod, i.size): i
                for i in data_items
            }
            removed_items: list[str] = []
            for (filename, mod, size), thumb_path in db_items_dict.items():
                if (filename, mod, size) in data_items_dict:
                    data_item = data_items_dict[(filename, mod, size)]
                    data_item.img_array = Utils.read_thumb(thumb_path)
                    if data_item.img_array is not None:
                        queue.put(data_item)
                    else:
                        print("img loader img array is none")
                        data_item.filename
                else:
                    removed_items.append(thumb_path)

            removed_items = ImgLoader._remove_from_disk(removed_items)
            ImgLoader._remove_records(img_item, removed_items)

            new_items: list[DataItem] = []
            for (filename, mod, size), data_item in data_items_dict.items():
                if (filename, mod, size) not in db_items_dict:

                    img = ImgUtils.read_img(data_item.abs_path)
                    data_item.img_array = ImgUtils.resize(img, Static.max_thumb_size)

                    rel_filepath = os.path.join(rel_parent, filename)
                    data_item.thumb_path = Utils.create_thumb_path(
                        path=rel_filepath,
                        fs_id=fs_id
                    )

                    new_items.append(data_item)
                    queue.put(data_item)

            ImgLoader._write_to_disk(new_items)
            ImgLoader._insert_records(img_item, new_items)

    def _remove_from_disk(paths: list[str]):
        result = []
        for thumb_path in paths:
            try:
                os.remove(thumb_path)
                result.append(thumb_path)
            except Exception as e:
                pass
            try:
                os.rmdir(os.path.dirname(thumb_path))
            except OSError as e:
                ...
        return result

    @staticmethod
    def _write_to_disk(data_items: list[DataItem]):
        for i in data_items:
            Utils.write_thumb(
                thumb_path=i.thumb_path,
                thumb_array=i.img_array
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
                CacheTable.thumb_path.name: i.thumb_path,
                CacheTable.size.name: i.size,
                CacheTable.mod.name: i.mod,
                CacheTable.rating.name: 0
            })
        stmt = (
            sqlalchemy.insert(CacheTable.table)
        )
        img_item.conn.execute(stmt, values)

    @staticmethod
    def _get_records(img_item: ImgLoaderItem):
        clmns = (
            CacheTable.thumb_path,
            CacheTable.filename,
            CacheTable.mod,
            CacheTable.size
        )
        stmt = (
            sqlalchemy.select(*clmns)
            .where(CacheTable.fs_id==img_item.fs_id)
            .where(CacheTable.rel_parent==img_item.rel_parent)
        )
        return img_item.conn.execute(stmt)
    
    def _remove_records(img_item: ImgLoaderItem, paths: list[str]):
        if not paths:
            return
        stmt = (
            sqlalchemy.delete(CacheTable.table)
            .where(CacheTable.fs_id==img_item.fs_id)
            .where(CacheTable.rel_parent==img_item.rel_parent)
            .where(CacheTable.thumb_path.in_(paths))
        )
        img_item.conn.execute(stmt)


class ReadImg:
    @staticmethod
    def start(src: str, desaturate: bool, queue: Queue):
        img_array = ImgUtils.read_img(src)
        queue.put((src, img_array))


class _DirChangedHandler(FileSystemEventHandler):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def on_any_event(self, event):
        self.callback(event)


class DirWatcher:
    @staticmethod
    def start(path: str, queue: Queue):
        if not path or not os.path.exists(path):
            return
        observer = Observer()
        handler = _DirChangedHandler(lambda e: queue.put(e))
        observer.schedule(handler, path, recursive=False)
        observer.start()
        try:
            while True:
                sleep(1)
                if not os.path.exists(path):
                    break
        finally:
            observer.stop()
            observer.join()


class PathFixer:
    @staticmethod
    def start(path: str, queue: Queue):
        if not path:
            result = PathFixerItem(None, None)
        elif os.path.exists(path):
            result = PathFixerItem(path, os.path.isdir(path))
        else:
            path_finder = PathFinder(path)
            fixed_path = path_finder.get_result()
            if fixed_path is not None:
                result = PathFixerItem(fixed_path, os.path.isdir(fixed_path))
            else:
                result = PathFixerItem(None, None)
        queue.put(result)


class JpgConverter:
    @staticmethod
    def start(jpg_item: JpgConvertItem, queue: Queue):
        jpg_item._urls = [
            i
            for i in jpg_item._urls
            if i.endswith(ImgUtils.ext_all)
        ]
        jpg_item._urls.sort(key=lambda p: os.path.getsize(p))

        filename = ""
        new_urls: list[str] = []

        for count, url in enumerate(jpg_item._urls, start=1):
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
    def start(data_items: list[DataItem], show_hidden: bool, queue: Queue):
        info_item = MultipleInfoItem()

        try:
            MultipleInfo._task(data_items, info_item, show_hidden)
            info_item.total_size = SharedUtils.get_f_size(info_item.total_size)
            info_item.total_files = len(list(info_item._files_set))
            info_item.total_files = format(info_item.total_files, ",").replace(",", " ")
            info_item.total_folders = len(list(info_item._folders_set))
            info_item.total_folders = format(info_item.total_folders, ",").replace(",", " ")
            queue.put(info_item)

        except Exception as e:
            print("tasks, MultipleInfoFiles error", e)
            info_item.total_size = MultipleInfo.err
            info_item.total_files = MultipleInfo.err
            info_item.total_folders = MultipleInfo.err
            queue.put(info_item)

    @staticmethod
    def _task(items: list[dict], info_item: MultipleInfoItem, show_hidden: bool):
        for i in items:
            if i["type_"] == Static.folder_type:
                MultipleInfo.get_folder_size(i, info_item, show_hidden)
                info_item._folders_set.add(i["src"])
            else:
                info_item.total_size += i["size"]
                info_item._files_set.add(i["src"])

    @staticmethod
    def get_folder_size(item: dict, info_item: MultipleInfoItem, show_hidden: bool):
        stack = [item["src"]]
        while stack:
            current_dir = stack.pop()
            try:
                os.listdir(current_dir)
            except Exception as e:
                print("tasks, MultipleItemsInfo error", e)
                continue
            for entry in os.scandir(current_dir):
                if entry.is_dir():
                    info_item._folders_set.add(item["src"])
                    stack.append(entry.path)
                else:
                    if show_hidden:
                        info_item.total_size += entry.stat().st_size
                        info_item._files_set.add(entry.path)
                    if not entry.name.startswith(Static.hidden_symbols):
                        info_item.total_size += entry.stat().st_size
                        info_item._files_set.add(entry.path)


class CopyWorker(BaseProcessWorker):
    def __init__(self, target, args):
        self.process_queue = Queue()
        self.gui_queue = Queue()
        super().__init__(target, (*args, self.process_queue, self.gui_queue))


class CopyTask:
    @staticmethod
    def start(copy_item: CopyItem, process_queue: Queue, gui_queue: Queue):

        if copy_item.is_search or copy_item.src_dir != copy_item.dst_dir:
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
                process_queue.put(copy_item)
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
                CopyTask.copy_file_with_progress(process_queue, copy_item, src, dest)
            except Exception as e:
                print("CopyTask copy error", e)
                copy_item.msg = "error"
                process_queue.put(copy_item)
                return
            if copy_item.is_cut and not copy_item.is_search:
                os.remove(src)
                "удаляем файлы чтобы очистить директории"

        if copy_item.is_cut and not copy_item.is_search:
            for src, dst in src_dst_urls:
                if src.is_dir() and src.exists():
                    try:
                        shutil.rmtree(src)
                    except Exception as e:
                        print("copy task error dir remove", e)
        
        copy_item.msg = "finished"
        process_queue.put(copy_item)

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
    def copy_file_with_progress(process_queue: Queue, copy_item: CopyItem, src: Path, dest: Path):
        block = 4 * 1024 * 1024  # 4 MB
        with open(src, "rb") as fsrc, open(dest, "wb") as fdst:
            while True:
                buf = fsrc.read(block)
                if not buf:
                    break
                fdst.write(buf)
                copy_item.current_size += len(buf) // 1024
                process_queue.put(copy_item)
        try:
            shutil.copystat(src, dest, follow_symlinks=True)
        except OSError:
            print("copy stat error CopyTask")


class SearchTaskWorker(BaseProcessWorker):
    """
    - args: любые аргументы
    - proq_q, gui_q: передаются автоматически
    """
    def __init__(self, target, args):
        self.process_queue = Queue()
        self.gui_queue = Queue()
        super().__init__(target, (*args, self.process_queue, self.gui_queue))


class SearchTask:
    sleep_s = 0

    @staticmethod
    def start(search_item: SearchItem, process_queue: Queue, gui_queue: Queue):
        engine = Dbase.create_engine()
        search_item.conn = Dbase.get_conn(engine)

        search_item.process_queue = process_queue
        search_item.gui_queue = gui_queue
        search_item.missed_files = search_item.search_list

        SearchTask.setup(search_item)

        SearchTask.scandir_recursive(search_item)
        search_item.process_queue.put(search_item)
        Dbase.close_conn(search_item.conn)

    @staticmethod
    def setup(search_item: SearchItem):
        for i in search_item.search_list:
            search_item.search_list_low.append(i.lower())

    # базовый метод обработки os.DirEntry
    @staticmethod
    def process_entry(entry: os.DirEntry, search_item: SearchItem):
        for i in search_item.search_list_low:
            if i in entry.name.lower():
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
                SearchTask.scan_current_dir(current_dir, dirs_list, search_item)
            except OSError as e:
                Utils.print_error()
                continue
            except Exception as e:
                Utils.print_error()
                continue
    
    @staticmethod
    def scan_current_dir(current_dir: str, dir_list: list, search_item: SearchItem):
        for entry in os.scandir(current_dir):
            if entry.name.startswith(Static.hidden_symbols):
                continue
            if entry.is_dir():
                dir_list.append(entry.path)
            if SearchTask.process_entry(entry, search_item):
                SearchTask.process_data_item(entry, search_item)

    @staticmethod
    def process_data_item(entry: os.DirEntry, search_item: SearchItem):
        # если мы нашли айтем из списка, то удаляем его из списка
        # не найденных айтемов
        for i in search_item.missed_files:
            if i.lower() in entry.name.lower():
                search_item.missed_files.remove(i)

        data_item = DataItem(entry.path)
        data_item.set_properties()

        if not entry.name.endswith(ImgUtils.ext_all):
            data = (data_item, search_item.missed_files)
            search_item.process_queue.put(data)
            sleep(SearchTask.sleep_s)
            return

        data_item.set_hash_and_thumb_path()
        # if os.path.exists(data_item.thumb_path):
        #     img_array = Utils.read_thumb(data_item.thumb_path)
        # else:
        #     img_array = ImgUtils.read_img(entry.path)
        #     img_array = ImgUtils.resize(img_array, Static.max_thumb_size)
        #     os.makedirs(
        #         os.path.dirname(data_item.thumb_path),
        #         exist_ok=True
        #     )
        #     Utils.write_thumb(
        #         data_item.thumb_path,
        #         img_array
        #     )
        #     stmt = (
        #         sqlalchemy.insert(CacheTable.table)
        #         .values({
        #             CacheTable.name.name: data_item.filename,
        #             CacheTable.type.name: data_item.type_,
        #             CacheTable.size.name: data_item.size,
        #             CacheTable.birth.name: data_item.birth,
        #             CacheTable.mod.name: data_item.mod,
        #             CacheTable.last_read.name: Utils.get_now(),
        #             CacheTable.rating.name: 0,
        #             CacheTable.partial_hash.name: data_item.partial_hash,
        #             CacheTable.thumb_path.name: data_item.thumb_path
        #         })
        #     )
        #     search_item.conn.execute(stmt)
        #     search_item.conn.commit()
        # data_item.img_array = img_array
        data = (data_item, search_item.missed_files)
        search_item.process_queue.put(data)
        sleep(SearchTask.sleep_s)
