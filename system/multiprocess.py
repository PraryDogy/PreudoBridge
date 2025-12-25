from multiprocessing import Process, Queue
import os
from system.shared_utils import PathFinder
from system.items import DataItem, MainWinItem, SortItem
from cfg import Static, JsonData



class MultiprocessRunner:
    def __init__(self, target: object, args: tuple):
        super().__init__()
        self.mp_queue = Queue()
        self.target = target
        self.args = args

    def start(self):
        self.proc = Process(target=self.target, args=self.args)
        self.proc.start()


class FinderItemsLoader:
    def __init__(self):
        super().__init__()

    def start(self, main_dir: MainWinItem, sort_item: SortItem, show_hidden: bool, out_q: Queue):
        items = []
        hidden_syms = () if show_hidden else Static.hidden_symbols

        fixed_path = PathFinder(main_dir).get_result()
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