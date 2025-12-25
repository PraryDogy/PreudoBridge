что делает эта задача
она подключается через sql alchemy к базе данных sql lite
обходит директорию и создает DataItem
DataItem это просто класс с набором свойств


class FinderItemsLoader(QRunnable):

    class Sigs(QObject):
        finished_ = pyqtSignal(dict)

    hidden_syms: tuple[str] = ()
    sql_errors = (IntegrityError, OperationalError)

    def __init__(self, main_win_item: MainWinItem, sort_item: SortItem):
        """
        Вернет словарик
        {"path": str путь,  "data_items": [DataItem, DataItem, ...]
        """

        super().__init__()
        self.sigs = FinderItemsLoader.Sigs()
        self.sort_item = sort_item
        self.main_win_item = main_win_item

        self.finder_items: dict[str, DataItem] = {}
        self.db_items: dict[str, int] = {}
        self.conn = Dbase.get_conn(Dbase.engine)

        if not JsonData.show_hidden:
            self.hidden_syms = Static.hidden_symbols

    def task(self):
        try:
            self._task()
        except Exception as e:
            print("tasks, FinderItems error", e)
            import traceback
            print(traceback.format_exc())

    def _task(self):
        items: list[DataItem] = []
        path_finder = PathFinder(self.main_win_item.main_dir)
        fixed_path = path_finder.get_result()

        if fixed_path is None:
            self.sigs.finished_.emit({"path": None, "data_items": items})
            return

        for i, path in enumerate(self._get_paths(fixed_path)):
            item = DataItem(path)
            item.set_properties()
            items.append(item)

        items = DataItem.sort_(items, self.sort_item)
        self.sigs.finished_.emit({"path": fixed_path, "data_items": items})

    def _get_paths(self, fixed_path: str):
        for entry in os.scandir(fixed_path):
            if entry.name.startswith(self.hidden_syms):
                continue
            if not os.access(entry.path, 4):
                print("tasks, finder items loader, get paths, access deined", entry.path)
                continue
            yield entry.path