from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import TypeVar

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from flutter_test_coverage.config import DEFAULT_LCOV_PATH, DEFAULT_LOW_COVERAGE_THRESHOLD
from flutter_test_coverage.coverage_report import (
    get_uncovered_lines as file_uncovered_lines,
)
from flutter_test_coverage.coverage_report import (
    list_low_coverage,
    summarize,
)
from flutter_test_coverage.lcov_parser import FileCoverage, parse_lcov
from flutter_test_coverage.missing_tests import (
    find_missing_test_files as scan_missing_test_files,
)

server = MCPServer(
    "flutter-test-coverage",
    instructions=(
        "Parses a Flutter project's lcov coverage report to find low-coverage files, uncovered "
        "lines, and source files with no matching test. This server does not run Flutter or its "
        "test suite -- run `flutter test --coverage` yourself first so the project's "
        f"{DEFAULT_LCOV_PATH} exists."
    ),
)

T = TypeVar("T")

# See dev_environment/server.py: MCPServer redacts a plain exception's message from the caller
# by default and only preserves a deliberately-raised ToolError's -- this surfaces safe,
# specific parsing/validation error text instead of a generic one.
KNOWN_SAFE_ERRORS = (ValueError, FileNotFoundError)


def surface_known_errors(fn: Callable[..., T]) -> Callable[..., T]:
    @wraps(fn)
    def wrapper(*args: object, **kwargs: object) -> T:
        try:
            return fn(*args, **kwargs)
        except KNOWN_SAFE_ERRORS as exc:
            raise ToolError(str(exc)) from exc

    return wrapper


def _resolve_lcov_path(project_path: str, lcov_path: str) -> Path:
    path = Path(lcov_path)
    return path if path.is_absolute() else Path(project_path) / path


def _load_coverage(project_path: str, lcov_path: str) -> dict[str, FileCoverage]:
    path = _resolve_lcov_path(project_path, lcov_path)
    if not path.is_file():
        raise FileNotFoundError(
            f"No coverage report at {path} -- run `flutter test --coverage` first."
        )
    return parse_lcov(path.read_text(encoding="utf-8"))


@server.tool()
@surface_known_errors
def parse_coverage_report(project_path: str, lcov_path: str = DEFAULT_LCOV_PATH) -> dict:
    """Parses a project's lcov coverage report and summarizes it: total files with coverage
    data, overall line coverage percentage, and line coverage percentage per directory."""
    files = _load_coverage(project_path, lcov_path)
    return summarize(files)


@server.tool()
@surface_known_errors
def list_low_coverage_files(
    project_path: str,
    lcov_path: str = DEFAULT_LCOV_PATH,
    threshold: float = DEFAULT_LOW_COVERAGE_THRESHOLD,
) -> list[dict]:
    """Lists source files whose line coverage percentage is below the given threshold, sorted
    ascending by coverage percentage."""
    files = _load_coverage(project_path, lcov_path)
    return list_low_coverage(files, threshold)


@server.tool()
@surface_known_errors
def get_uncovered_lines(
    project_path: str, file_path: str, lcov_path: str = DEFAULT_LCOV_PATH
) -> list[int]:
    """Returns the line numbers of `file_path` that have zero test coverage, according to the
    project's lcov report. `file_path` must match a path as recorded by lcov's SF: records."""
    files = _load_coverage(project_path, lcov_path)
    if file_path not in files:
        raise ValueError(f"No coverage data for {file_path}")
    return file_uncovered_lines(files[file_path])


@server.tool()
@surface_known_errors
def find_missing_test_files(project_path: str) -> list[dict]:
    """Scans a Flutter project's lib/ directory for source files with no matching test file
    under test/, skipping generated (.g.dart/.freezed.dart) files."""
    return scan_missing_test_files(Path(project_path))


if __name__ == "__main__":
    server.run()
