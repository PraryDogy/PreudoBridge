import os
import stat
from collections import defaultdict

import sqlalchemy
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from cfg import Static
from system.database import DirTable


class DirIndex:
    """
    Доступ к кэшу дерева директорий (таблица dir_index).

    mtime папки меняется только когда внутри неё напрямую создаётся,
    удаляется или переименовывается элемент. Если mtime совпадает с
    сохранённым, список подпапок не изменился и listing не нужен.
    """

    def __init__(self, engine: sqlalchemy.Engine):
        self.engine = engine

    def get_dirs(self, root: str) -> list[str]:
        root = os.path.normpath(root)

        if not os.path.isdir(root):
            self._save(upserts=[], drop=[root])
            return []

        with self.engine.connect() as conn:
            mtimes, children_of = self._load_subtree(conn, root)

        result: list[str] = []
        stack = [root]
        upserts: list[tuple[str, str, int]] = []
        drop: list[str] = []

        while stack:
            current = stack.pop()
            try:
                st = os.stat(current)
            except OSError:
                drop.append(current)
                continue

            if not stat.S_ISDIR(st.st_mode):
                drop.append(current)
                continue

            result.append(current)

            if mtimes.get(current) == st.st_mtime_ns:
                subdirs = children_of.get(current, [])
            else:
                subdirs = self._list_subdirs(current)
                if subdirs is None:
                    continue
                old = set(children_of.get(current, []))
                drop.extend(old - set(subdirs))
                upserts.append(
                    (current, os.path.dirname(current), st.st_mtime_ns)
                )
                children_of[current] = subdirs

            stack.extend(subdirs)

        self._save(upserts, drop)
        return result

    @staticmethod
    def _subtree_filter(path: str):
        # без LIKE, чтобы % и _ в именах папок не ломали выборку
        prefix = path if path.endswith(os.sep) else path + os.sep
        return sqlalchemy.or_(
            DirTable.path == path,
            sqlalchemy.func.substr(DirTable.path, 1, len(prefix)) == prefix,
        )

    def _load_subtree(self, conn: sqlalchemy.Connection, root: str):
        stmt = (
            sqlalchemy.select(DirTable.path, DirTable.parent, DirTable.mtime_ns)
            .where(self._subtree_filter(root))
        )
        mtimes: dict[str, int] = {}
        children_of: dict[str, list[str]] = defaultdict(list)
        for path, parent, mtime in conn.execute(stmt):
            mtimes[path] = mtime
            children_of[parent].append(path)
        return mtimes, children_of

    @staticmethod
    def _list_subdirs(path: str) -> list[str] | None:
        result: list[str] = []
        try:
            with os.scandir(path) as it:
                for entry in it:
                    if entry.name.startswith(Static.hidden_symbols):
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        result.append(entry.path)
        except OSError:
            return None
        return result

    def _save(self, upserts, drop):
        if not upserts and not drop:
            return

        with self.engine.begin() as conn:
            for path in drop:
                conn.execute(
                    sqlalchemy.delete(DirTable.table)
                    .where(self._subtree_filter(path))
                )

            if upserts:
                rows = [
                    {"path": p, "parent": par, "mtime_ns": m}
                    for p, par, m in upserts
                ]
                stmt = sqlite_insert(DirTable.table)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["path"],
                    set_={
                        "parent": stmt.excluded.parent,
                        "mtime_ns": stmt.excluded.mtime_ns,
                    },
                )
                conn.execute(stmt, rows)