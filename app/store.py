"""A small partitioned document store.

This is meant to emulate an object database like DynamoDB. You are free to update
the internals (but it's not required), but not the public API.

Every document is addressed by a pair: a **partition key** saying which group it
belongs to, and a **sort key** identifying it within that group.

    store.put("results:user-1", "2026-09-01T09:00:00", draw)
    store.get("results:user-1", "2026-09-01T09:00:00", ResultsDocument)

There are no indexes and no queries across fields. Three ways to find something:

    get(pk, sk)            one document, if you know both keys, cheap
    query(pk)             everything in one partition, in sort-key order
    scan(pk_prefix)       everything across partitions — expensive, see below

Reads are typed or not, per call site:

    store.get(pk, sk, Member)     -> Member, validated
    store.get(pk, sk)             -> dict, exactly as stored

The typed form fails loudly when a document has drifted out of shape, and it is
what the application code uses.

Writes can be single-document or batched:

    store.put(pk, sk, value)
    store.put_many([(pk, sk, value), ...])

You can delete individual documents:

    store.delete(pk, sk)

This is the whole public surface: get, query, keys, scan, put, put_many, delete,
close. It is pinned by tests/test_store_api.py.

Backed by SQLite so writes are atomic and durable + it behaves the same everywhere.
That is an implementation detail. You may rely only on the documented public API.
"""

import json
import logging
import sqlite3
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any, TypeVar, overload

from pydantic import BaseModel

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "dev.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    pk     TEXT NOT NULL,
    sk     TEXT NOT NULL,
    value  TEXT NOT NULL,
    PRIMARY KEY (pk, sk)
)
"""

T = TypeVar("T", bound=BaseModel)

# Sorts after every character we use in keys, so key + this bounds a range.
_HIGH = "\uffff"


def _encode(value: BaseModel | dict[str, Any]) -> str:
    if isinstance(value, BaseModel):
        return value.model_dump_json()
    return json.dumps(value, separators=(",", ":"))


def _decode[T: BaseModel](raw: str, model: type[T] | None) -> Any:
    return model.model_validate_json(raw) if model else json.loads(raw)


class Store:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path or DB_PATH)
        # check_same_thread=False because FastAPI runs sync dependencies in a
        # threadpool and may run a generator dependency's cleanup on a different
        # thread than its setup.
        self.conn = sqlite3.connect(
            self.path, isolation_level=None, check_same_thread=False
        )
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    @overload
    def get(self, pk: str, sk: str, model: type[T]) -> T | None: ...

    @overload
    def get(self, pk: str, sk: str, model: None = None) -> dict[str, Any] | None: ...

    def get(self, pk: str, sk: str, model: type[T] | None = None) -> Any:
        """One document, or None."""
        logging.info("store:get pk=%s, sk=%s", pk, sk)
        row = self.conn.execute(
            "SELECT value FROM documents WHERE pk = ? AND sk = ?", (pk, sk)
        ).fetchone()
        return _decode(row[0], model) if row else None

    @overload
    def query(
        self,
        pk: str,
        model: type[T],
        *,
        start: str | None = None,
        end: str | None = None,
    ) -> Iterator[tuple[str, T]]: ...

    @overload
    def query(
        self,
        pk: str,
        model: None = None,
        *,
        start: str | None = None,
        end: str | None = None,
    ) -> Iterator[tuple[str, dict[str, Any]]]: ...

    def query(
        self,
        pk: str,
        model: type[T] | None = None,
        *,
        start: str | None = None,
        end: str | None = None,
    ) -> Iterator[tuple[str, Any]]:
        """Yield (sort_key, document) from one partition, in sort-key order.

        `start` is inclusive and `end` is exclusive, both compared against sort keys.

        Lazy. Documents are read one at a time as you consume them, so what you do
        not consume, you do not pay for.
        """
        logging.info(
            "store:query pk=%s, model=%s, start=%s, end=%s",
            pk,
            model,
            start,
            end,
        )
        cursor = self.conn.execute(
            "SELECT sk, value FROM documents"
            " WHERE pk = ? AND sk >= ? AND sk < ? ORDER BY sk",
            (pk, start or "", end or _HIGH),
        )
        for sk, value in cursor:
            yield sk, _decode(value, model)

    def keys(
        self, pk: str, *, start: str | None = None, end: str | None = None
    ) -> Iterator[str]:
        """Yield sort keys from one partition. Nothing is read or validated."""
        logging.info(
            "store:keys pk=%s, start=%s, end=%s",
            pk,
            start,
            end,
        )
        cursor = self.conn.execute(
            "SELECT sk FROM documents WHERE pk = ? AND sk >= ? AND sk < ? ORDER BY sk",
            (pk, start or "", end or _HIGH),
        )
        for (sk,) in cursor:
            yield sk

    @overload
    def scan(
        self,
        pk_prefix: str = "",
        model: type[T] = ...,
    ) -> Iterator[tuple[str, str, T]]: ...

    @overload
    def scan(
        self,
        pk_prefix: str = "",
        model: None = None,
    ) -> Iterator[tuple[str, str, dict[str, Any]]]: ...

    def scan(
        self, pk_prefix: str = "", model: type[T] | None = None
    ) -> Iterator[tuple[str, str, Any]]:
        """Yield (partition_key, sort_key, document) across partitions.

        Every partition whose key starts with `pk_prefix`, or all of them if empty.
        """
        logging.info("store:scan pk_prefix=%s, model=%s", pk_prefix, model)
        cursor = self.conn.execute(
            "SELECT pk, sk, value FROM documents"
            " WHERE pk >= ? AND pk < ? ORDER BY pk, sk",
            (pk_prefix, pk_prefix + _HIGH),
        )
        for pk, sk, value in cursor:
            yield pk, sk, _decode(value, model)

    def put(self, pk: str, sk: str, value: BaseModel | dict[str, Any]) -> None:
        logging.info("store:put pk=%s, sk=%s", pk, sk)
        self.conn.execute(
            "INSERT INTO documents (pk, sk, value) VALUES (?, ?, ?)"
            " ON CONFLICT(pk, sk) DO UPDATE SET value = excluded.value",
            (pk, sk, _encode(value)),
        )

    def put_many(
        self, items: Iterable[tuple[str, str, BaseModel | dict[str, Any]]]
    ) -> int:
        """Write many documents in one transaction."""
        logging.info("store:put_many")
        rows = [(pk, sk, _encode(value)) for pk, sk, value in items]
        self.conn.execute("BEGIN")
        self.conn.executemany(
            "INSERT INTO documents (pk, sk, value) VALUES (?, ?, ?)"
            " ON CONFLICT(pk, sk) DO UPDATE SET value = excluded.value",
            rows,
        )
        self.conn.execute("COMMIT")
        return len(rows)

    def delete(self, pk: str, sk: str) -> None:
        logging.info("store:delete pk=%s, sk=%s", pk, sk)
        self.conn.execute("DELETE FROM documents WHERE pk = ? AND sk = ?", (pk, sk))


def get_store() -> Iterator[Store]:
    """FastAPI dependency."""
    store = Store()
    try:
        yield store
    finally:
        store.close()
