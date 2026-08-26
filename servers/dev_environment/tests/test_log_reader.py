import pytest

from dev_environment.log_reader import tail_log


@pytest.fixture(name="log_dir")
def log_dir_fixture(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "app.log").write_text("\n".join(f"line {i}" for i in range(1, 11)) + "\n")
    return log_dir


def test_tail_log_returns_last_n_lines(log_dir):
    lines = tail_log(log_dir, "app.log", lines=3)
    assert lines == ["line 8", "line 9", "line 10"]


def test_tail_log_returns_whole_file_when_shorter_than_requested(log_dir):
    lines = tail_log(log_dir, "app.log", lines=100)
    assert len(lines) == 10


def test_tail_log_rejects_path_traversal(log_dir):
    with pytest.raises(ValueError, match="escapes"):
        tail_log(log_dir, "../secrets.txt", lines=10)


def test_tail_log_rejects_missing_file(log_dir):
    with pytest.raises(ValueError, match="No such log file"):
        tail_log(log_dir, "missing.log", lines=10)


def test_tail_log_rejects_nested_traversal(log_dir):
    with pytest.raises(ValueError, match="escapes"):
        tail_log(log_dir, "subdir/../../secrets.txt", lines=10)
