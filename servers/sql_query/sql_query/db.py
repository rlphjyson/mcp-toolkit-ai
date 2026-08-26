import os
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import sqlalchemy as sa

from sql_query.config import DATABASE_URL, HARD_MAX_ROWS, QUERY_TIMEOUT_SECONDS
from sql_query.query_safety import validate_select_only

_executor = ThreadPoolExecutor(max_workers=4)


class QueryTimeoutError(Exception):
    pass


@dataclass
class ColumnInfo:
    name: str
    type: str
    nullable: bool


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[list]
    truncated: bool


def _sqlite_file_path(database_url: str) -> str | None:
    # Deliberately not urlparse+lstrip("/"): SQLAlchemy's own convention is that everything
    # after the literal "sqlite:///" prefix IS the filesystem path verbatim -- "sqlite:///rel/db"
    # (3 slashes) is relative, "sqlite:////abs/db" (4 slashes) is absolute, distinguished only by
    # whether that remainder itself starts with "/". lstrip("/") strips *all* leading slashes,
    # which silently turns an absolute POSIX path into a relative one (caught the hard way: this
    # passed on Windows, where db paths don't start with "/", and failed in Linux CI).
    if ":memory:" in database_url or not database_url.startswith("sqlite:///"):
        return None
    return database_url[len("sqlite:///") :]


def _ensure_sqlite_dir_exists(database_url: str) -> None:
    db_path = _sqlite_file_path(database_url)
    if db_path is None:
        return
    parent = Path(db_path).parent
    if str(parent) not in ("", "."):
        os.makedirs(parent, exist_ok=True)


@lru_cache
def get_engine() -> sa.Engine:
    _ensure_sqlite_dir_exists(DATABASE_URL)
    return sa.create_engine(DATABASE_URL)


def list_tables() -> list[str]:
    inspector = sa.inspect(get_engine())
    return sorted(inspector.get_table_names())


def describe_table(table: str) -> list[ColumnInfo]:
    known_tables = set(list_tables())
    if table not in known_tables:
        raise ValueError(f"Unknown table '{table}'.")

    inspector = sa.inspect(get_engine())
    return [
        ColumnInfo(name=col["name"], type=str(col["type"]), nullable=col["nullable"])
        for col in inspector.get_columns(table)
    ]


def _execute(sql: str, max_rows: int) -> QueryResult:
    with get_engine().connect() as conn:
        result = conn.execute(sa.text(sql))
        columns = list(result.keys())
        rows = result.fetchmany(max_rows + 1)
        truncated = len(rows) > max_rows
        return QueryResult(
            columns=columns,
            rows=[list(row) for row in rows[:max_rows]],
            truncated=truncated,
        )


def run_query(sql: str, max_rows: int) -> QueryResult:
    """Validates `sql` is a single read-only SELECT, then executes it with a row cap and a
    best-effort timeout.

    The timeout is enforced by waiting on a worker thread with a deadline, not by cancelling the
    underlying DB call -- Python can't forcibly kill a thread mid I/O. A query that blows the
    timeout will still finish running in the background; this bounds how long the *caller* waits,
    which is the practical concern for an interactively-used tool, not a guarantee the database
    stops working immediately. Document this rather than pretend otherwise.
    """
    validate_select_only(sql)
    max_rows = min(max_rows, HARD_MAX_ROWS)

    future = _executor.submit(_execute, sql, max_rows)
    try:
        return future.result(timeout=QUERY_TIMEOUT_SECONDS)
    except FutureTimeoutError as exc:
        raise QueryTimeoutError(
            f"Query did not complete within {QUERY_TIMEOUT_SECONDS}s."
        ) from exc
