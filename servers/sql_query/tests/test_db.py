import time

import pytest
import sqlalchemy as sa

from sql_query import db
from sql_query.db import QueryTimeoutError


@pytest.fixture(name="engine")
def engine_fixture(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db, "DATABASE_URL", f"sqlite:///{db_path}")
    db.get_engine.cache_clear()

    engine = sa.create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"))
        for i in range(5):
            conn.execute(sa.text("INSERT INTO users (name) VALUES (:name)"), {"name": f"user{i}"})

    yield engine
    db.get_engine.cache_clear()


def test_get_engine_creates_missing_parent_directory(tmp_path, monkeypatch):
    # Regression test: SQLite does not create a database file's parent directory itself, so a
    # fresh checkout using the default DATABASE_URL (sqlite:///./data/sample.db) would fail with
    # "unable to open database file" the first time anyone actually ran the server -- caught by
    # a live CLI smoke test, not by the rest of this suite, since the other fixtures all point
    # at tmp_path itself, which pytest already creates.
    nested_db_path = tmp_path / "nested" / "does" / "not" / "exist" / "test.db"
    monkeypatch.setattr(db, "DATABASE_URL", f"sqlite:///{nested_db_path}")
    db.get_engine.cache_clear()

    db.get_engine()

    assert nested_db_path.parent.is_dir()
    db.get_engine.cache_clear()


def test_list_tables_returns_created_table(engine):
    assert db.list_tables() == ["users"]


def test_describe_table_returns_columns(engine):
    columns = db.describe_table("users")
    names = {c.name for c in columns}
    assert names == {"id", "name"}


def test_describe_table_rejects_unknown_table(engine):
    with pytest.raises(ValueError, match="Unknown table"):
        db.describe_table("does_not_exist")


def test_run_query_returns_rows_and_columns(engine):
    result = db.run_query("SELECT id, name FROM users ORDER BY id", max_rows=100)

    assert result.columns == ["id", "name"]
    assert len(result.rows) == 5
    assert result.truncated is False


def test_run_query_truncates_and_flags_it(engine):
    result = db.run_query("SELECT id FROM users ORDER BY id", max_rows=2)

    assert len(result.rows) == 2
    assert result.truncated is True


def test_run_query_rejects_non_select(engine):
    with pytest.raises(ValueError, match="Only SELECT"):
        db.run_query("DELETE FROM users", max_rows=10)


def test_run_query_caps_at_hard_max_even_if_caller_asks_for_more(engine, monkeypatch):
    monkeypatch.setattr(db, "HARD_MAX_ROWS", 3)
    result = db.run_query("SELECT id FROM users ORDER BY id", max_rows=1000)
    assert len(result.rows) == 3


def test_run_query_times_out_on_a_slow_query(engine, monkeypatch):
    def slow_execute(sql, max_rows):
        time.sleep(1)
        raise AssertionError("should have been abandoned by the timeout before finishing")

    monkeypatch.setattr(db, "_execute", slow_execute)
    monkeypatch.setattr(db, "QUERY_TIMEOUT_SECONDS", 0.05)

    with pytest.raises(QueryTimeoutError):
        db.run_query("SELECT 1", max_rows=10)
