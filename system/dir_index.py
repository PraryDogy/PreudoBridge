import os
import stat
import time
from collections import defaultdict

import sqlalchemy
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from cfg import Static
from system.database import DirTable

# mtime для папок, которые найдены, но ещё не просканированы
PENDING_MTIME = -1

# сброс пачки в БД: по количеству или по времени
FLUSH_EVERY = 50
FLUSH_INTERVAL = 1.0


class _Batch:
    def __init__(self):
        self.created = time.monotonic()
        self.upserts: list[tuple[str, str, int]] = []   # path, parent, mtime
        self.pending: list[tuple[str, str]] = []        # path, parent
        self.drop: list[str] = []

    def is_full(self) -> bool:
        size = len(self.upserts) + len(self.pending) + len(self.drop)
        return (
            size >= FLUSH_EVERY
            or time.monotonic() - self.created >= FLUSH_INTERVAL
        )


class DirIndex:
    """
    Доступ к кэшу дерева директорий (таблица dir_index, модель DirTable).

    mtime папки меняется только когда внутри неё напрямую создаётся,
    удаляется или переименовывается элемент. Если mtime совпадает с
    сохранённым, список подпапок не изменился и listing не нужен.

    Запись идёт пачками во время обхода. Папка и её подпапки всегда
    попадают в одну пачку, поэтому прерванный обход не оставляет папку
    без подпапок: непросканированные папки помечены PENDING_MTIME.
    """

    def __init__(self, engine: sqlalchemy.Engine):
        self.engine = engine

    def get_dirs(self, root: str) -> list[str]:
        root = os.path.normpath(root)
        batch = _Batch()

        if not os.path.isdir(root):
            batch.drop.append(root)
            self._save(batch)
            return []

        with self.engine.connect() as conn:
            mtimes, children_of = self._load_subtree(conn, root)

        result: list[str] = []
        stack = [root]

        while stack:
            current = stack.pop()
            try:
                st = os.stat(current)
            except OSError:
                batch.drop.append(current)
            else:
                if not stat.S_ISDIR(st.st_mode):
                    batch.drop.append(current)
                else:
                    result.append(current)
                    subdirs = self._resolve_children(
                        current, st.st_mtime_ns, mtimes, children_of, batch
                    )
                    stack.extend(subdirs)

            if batch.is_full():
                self._save(batch)
                batch = _Batch()

        self._save(batch)
        return result

    def _resolve_children(
        self,
        path: str,
        mtime: int,
        mtimes: dict[str, int],
        children_of: dict[str, list[str]],
        batch: _Batch,
    ) -> list[str]:
        if mtimes.get(path) == mtime:
            # папка не менялась: подпапки берем из кэша
            return children_of.get(path, [])

        subdirs = self._list_subdirs(path)
        if subdirs is None:
            # не смогли прочитать: не сохраняем, попробуем в следующий раз
            return []

        old = set(children_of.get(path, []))
        batch.drop.extend(old - set(subdirs))
        # папка и её подпапки в одной пачке
        batch.upserts.append((path, os.path.dirname(path), mtime))
        batch.pending.extend((sub, path) for sub in subdirs)
        children_of[path] = subdirs
        return subdirs

    @staticmethod
    def _subtree_filter(path: str):
        # без LIKE: % и _ в именах папок не ломают выборку
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

    def _save(self, batch: _Batch):
        if not (batch.drop or batch.pending or batch.upserts):
            return

        with self.engine.begin() as conn:
            # 1. удаляем пропавшие поддеревья
            for path in batch.drop:
                conn.execute(
                    sqlalchemy.delete(DirTable.table)
                    .where(self._subtree_filter(path))
                )

            # 2. новые подпапки (уже существующие не трогаем)
            if batch.pending:
                stmt = sqlite_insert(DirTable.table).on_conflict_do_nothing(
                    index_elements=["path"]
                )
                conn.execute(stmt, [
                    {"path": p, "parent": par, "mtime_ns": PENDING_MTIME}
                    for p, par in batch.pending
                ])

            # 3. просканированные папки с новым mtime
            if batch.upserts:
                stmt = sqlite_insert(DirTable.table)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["path"],
                    set_={
                        "parent": stmt.excluded.parent,
                        "mtime_ns": stmt.excluded.mtime_ns,
                    },
                )
                conn.execute(stmt, [
                    {"path": p, "parent": par, "mtime_ns": m}
                    for p, par, m in batch.upserts
                ])