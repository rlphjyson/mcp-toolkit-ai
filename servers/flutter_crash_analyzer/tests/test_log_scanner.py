import pytest

from flutter_crash_analyzer.log_scanner import search_log, tail_lines


@pytest.fixture(name="log_file")
def log_file_fixture(tmp_path):
    path = tmp_path / "app.log"
    path.write_text("\n".join(f"line {i}" for i in range(1, 11)) + "\n")
    return path


def test_tail_lines_returns_last_n_lines(log_file):
    assert tail_lines(log_file, 3) == ["line 8", "line 9", "line 10"]


def test_tail_lines_returns_whole_file_when_shorter_than_requested(log_file):
    assert len(tail_lines(log_file, 100)) == 10


def test_tail_lines_raises_file_not_found_for_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="No such log file"):
        tail_lines(tmp_path / "missing.log", 10)


def test_tail_lines_raises_value_error_for_directory(tmp_path):
    with pytest.raises(ValueError, match="Not a file"):
        tail_lines(tmp_path, 10)


def test_search_log_finds_matches(log_file):
    matches = search_log(log_file, r"line [12]$")
    assert matches == [
        {"line_number": 1, "line": "line 1"},
        {"line_number": 2, "line": "line 2"},
    ]


def test_search_log_respects_max_matches(log_file):
    matches = search_log(log_file, r"line", max_matches=2)
    assert len(matches) == 2


def test_search_log_raises_value_error_for_invalid_regex(log_file):
    with pytest.raises(ValueError, match="Invalid regex pattern"):
        search_log(log_file, r"[unclosed")


def test_search_log_raises_file_not_found_for_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="No such log file"):
        search_log(tmp_path / "missing.log", r"anything")
