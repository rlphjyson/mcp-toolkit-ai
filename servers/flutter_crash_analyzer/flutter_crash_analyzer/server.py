from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import TypeVar

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from flutter_crash_analyzer.config import DEFAULT_MAX_LOG_MATCHES
from flutter_crash_analyzer.git_blame import blame_line
from flutter_crash_analyzer.log_scanner import search_log, tail_lines
from flutter_crash_analyzer.root_cause import tag_root_causes
from flutter_crash_analyzer.stack_trace import ParsedException, StackFrame, to_repo_relative_path
from flutter_crash_analyzer.stack_trace import parse_stack_trace as parse_trace

server = MCPServer(
    "flutter-crash-analyzer",
    instructions=(
        "Parses Flutter/Dart stack traces (both the boxed 'EXCEPTION CAUGHT BY' widgets-library "
        "format and the plain 'Unhandled exception:' format) and correlates frames pointing at "
        "the project's own source with git history to suggest likely root causes. Also scans and "
        "tails arbitrary log files."
    ),
)

T = TypeVar("T")

# See dev_environment/server.py and issue_tracker/server.py for why this exists: MCPServer
# redacts a plain exception's message from the caller by default and only preserves a
# deliberately-raised ToolError's -- this surfaces safe, specific validation/parsing error text
# instead of a generic one.
KNOWN_SAFE_ERRORS = (ValueError, FileNotFoundError)


def surface_known_errors(fn: Callable[..., T]) -> Callable[..., T]:
    @wraps(fn)
    def wrapper(*args: object, **kwargs: object) -> T:
        try:
            return fn(*args, **kwargs)
        except KNOWN_SAFE_ERRORS as exc:
            raise ToolError(str(exc)) from exc

    return wrapper


def _frame_dict(frame: StackFrame) -> dict:
    return {
        "index": frame.index,
        "function": frame.function,
        "file": frame.file,
        "line": frame.line,
        "column": frame.column,
        "is_project_code": frame.is_project_code,
    }


def _exception_dict(parsed: ParsedException) -> dict:
    return {
        "exception_type": parsed.exception_type,
        "message": parsed.message,
        "frames": [_frame_dict(f) for f in parsed.frames],
    }


@server.tool()
@surface_known_errors
def parse_stack_trace(trace_text: str, project_package_name: str = "") -> dict:
    """Parses raw Flutter/Dart exception text into a structured exception type, message, and
    stack frames. Handles both the boxed widgets-library exception format and the plain
    'Unhandled exception:' format. Pass `project_package_name` (the app's own Dart package name)
    so frames under `package:<project_package_name>/...` are flagged as project code."""
    parsed = parse_trace(trace_text, project_package_name or None)
    return _exception_dict(parsed)


@server.tool()
@surface_known_errors
def analyze_crash(trace_text: str, repo_path: str, project_package_name: str = "") -> dict:
    """Parses a crash trace, tags likely root causes from the exception type/message, and runs
    `git blame` on the first stack frame pointing at the project's own source to surface who
    last touched that line and when."""
    parsed = parse_trace(trace_text, project_package_name or None)
    root_cause_tags = tag_root_causes(parsed.exception_type, parsed.message)

    likely_culprit = None
    project_frame = next((f for f in parsed.frames if f.is_project_code and f.file and f.line), None)
    if project_frame is not None:
        assert project_frame.file is not None
        assert project_frame.line is not None
        repo_relative_file = to_repo_relative_path(project_frame.file, project_package_name or None)
        blame = blame_line(Path(repo_path), repo_relative_file, project_frame.line)
        likely_culprit = {"file": project_frame.file, "line": project_frame.line, "blame": blame}

    return {
        "exception_type": parsed.exception_type,
        "message": parsed.message,
        "root_cause_tags": root_cause_tags,
        "frames": [_frame_dict(f) for f in parsed.frames],
        "likely_culprit": likely_culprit,
    }


@server.tool()
@surface_known_errors
def search_log_file(path: str, pattern: str, max_matches: int = DEFAULT_MAX_LOG_MATCHES) -> list[dict]:
    """Searches a log file for lines matching a regex pattern, returning up to `max_matches`
    {line_number, line} matches."""
    return search_log(Path(path), pattern, max_matches)


@server.tool()
@surface_known_errors
def tail_log_file(path: str, lines: int = 100) -> list[str]:
    """Returns the last N lines of a log file."""
    return tail_lines(Path(path), lines)


if __name__ == "__main__":
    server.run()
