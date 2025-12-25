import os
from multiprocessing import Process, Queue

from cfg import JsonData, Static
from system.items import DataItem, MainWinItem, SortItem
from system.shared_utils import PathFinder


class ProcessWorker:
    def __init__(self, target: callable, args: tuple):
        # Создаём очередь для передачи данных из процесса в GUI
        self.queue = Queue()
        # Создаём процесс, который будет выполнять target(*args, queue)
        self.proc = Process(
            target=target,
            args=(*args, self.queue)
        )

    def start(self):
        # Запускаем процесс
        self.proc.start()

    def force_stop(self):
        # Принудительно останавливаем процесс, если он ещё жив
        if self.proc.is_alive():
            self.proc.terminate()  # посылаем сигнал terminate
            self.proc.join()       # ждём завершения процесса

        # Закрываем очередь и дожидаемся завершения её внутреннего потока
        if self.queue:
            self.queue.close()
            self.queue.join_thread()

    def get_queue(self):
        # Возвращает очередь для чтения данных из процесса
        return self.queue

    def close(self):
        # Корректно закрываем очередь
        if self.queue:
            self.queue.close()
            self.queue.join_thread()

        # Если процесс уже завершён, выполняем join для очистки ресурсов
        if self.proc and not self.proc.is_alive():
            self.proc.join()


class FinderItemsLoader:
    @staticmethod
    def start(main_win_item: MainWinItem, sort_item: SortItem, out_q: Queue):
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