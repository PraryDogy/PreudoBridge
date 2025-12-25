from multiprocessing import Process, Queue
import os
from system.shared_utils import PathFinder
from system.items import DataItem, MainWinItem, SortItem
from cfg import Static, JsonData


class MultiprocessRunner:
    def __init__(self, target, args):
        self.queue = Queue()
        self.proc = Process(
            target=target,
            args=(*args, self.queue)
        )

    def start(self):
        self.proc.start()

    def get_queue(self):
        return self.queue


class FinderItemsLoader:
    def __init__(self, main_win_item: MainWinItem, sort_item: SortItem, out_q: Queue):
        super().__init__()
        self.main_win_item = main_win_item
        self.sort_item = sort_item
        self.out_q = out_q

    def start(self):
        items = []
        hidden_syms = () if JsonData.show_hidden else Static.hidden_symbols

        fixed_path = PathFinder(self.main_win_item.main_dir).get_result()
        if fixed_path is None:
            self.out_q.put({"path": None, "data_items": []})
            return

        for entry in os.scandir(fixed_path):
            if entry.name.startswith(hidden_syms):
                continue
            if not os.access(entry.path, 4):
                continue

            item = DataItem(entry.path)
            item.set_properties()
            items.append(item)

        items = DataItem.sort_(items, self.sort_item)
        self.out_q.put({"path": fixed_path, "data_items": items})