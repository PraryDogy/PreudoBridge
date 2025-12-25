from multiprocessing import Process, Queue
import os
from system.shared_utils import PathFinder
from system.items import DataItem, MainWinItem, SortItem
from cfg import Static, JsonData


class Tasker:
    def __init__(self, target: callable, args: tuple):
        self.queue = Queue()
        self.proc = Process(
            target=target,
            args=(*args, self.queue)
        )

    def start(self):
        self.proc.start()

    def stop(self):
        if self.proc.is_alive():
            self.proc.terminate()
            self.proc.join()

    def get_queue(self):
        return self.queue

    def close(self):
        if self.queue:
            self.queue.close()
            self.queue.join_thread()

        if self.proc and not self.proc.is_alive():
            self.proc.join()


class Tasks:

    @staticmethod
    def load_finder_items(main_win_item: MainWinItem, sort_item: SortItem, out_q: Queue):
        items = []
        hidden_syms = () if JsonData.show_hidden else Static.hidden_symbols

        fixed_path = PathFinder(main_win_item.main_dir).get_result()
        if fixed_path is None:
            out_q.put({"path": None, "data_items": []})
            return

        for entry in os.scandir(fixed_path):
            if entry.name.startswith(hidden_syms):
                continue
            if not os.access(entry.path, 4):
                continue

            item = DataItem(entry.path)
            item.set_properties()
            items.append(item)

        items = DataItem.sort_(items, sort_item)
        out_q.put({"path": fixed_path, "data_items": items})