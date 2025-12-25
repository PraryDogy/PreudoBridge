from multiprocessing import Process, Queue
import os
from system.shared_utils import PathFinder
from system.items import DataItem
from cfg import Static


class FinderItemsLoader:
    def __init__(self):
        super().__init__()

    def start(self, main_dir, sort_item, show_hidden, out_q: Queue):
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