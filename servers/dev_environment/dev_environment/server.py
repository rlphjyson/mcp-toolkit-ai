import subprocess
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import TypeVar

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from dev_environment.config import DEFAULT_TEST_TIMEOUT_SECONDS, LOG_ALLOWED_DIR
from dev_environment.git_log import get_recent_commits
from dev_environment.log_reader import tail_log
from dev_environment.processes import list_processes
from dev_environment.test_runner import RunTimeoutError, run_tests

server = MCPServer(
    "dev-environment",
    instructions=(
        "Local dev environment awareness: running processes, recent git history, running a "
        "repo's test command, and tailing a log file. `tail_log`'s paths are relative to the "
        f"server's configured log directory ({LOG_ALLOWED_DIR}) and cannot escape it."
    ),
)

T = TypeVar("T")

# See codebase_intelligence/server.py and sql_query/server.py for why this exists: MCPServer
# redacts a plain exception's message from the caller by default and only preserves a
# deliberately-raised ToolError's -- this surfaces safe, specific validation/subprocess error
# text instead of a generic one.
KNOWN_SAFE_ERRORS = (ValueError, subprocess.CalledProcessError, RunTimeoutError)


def surface_known_errors(fn: Callable[..., T]) -> Callable[..., T]:
    @wraps(fn)
    def wrapper(*args: object, **kwargs: object) -> T:
        try:
            return fn(*args, **kwargs)
        except KNOWN_SAFE_ERRORS as exc:
            raise ToolError(str(exc)) from exc

    return wrapper


@server.tool()
@surface_known_errors
def list_running_processes(name_filter: str = "") -> list[dict]:
    """Lists running processes, optionally filtered by a case-insensitive substring of the
    process name."""
    return [
        {
            "pid": p.pid,
            "name": p.name,
            "username": p.username,
            "cpu_percent": p.cpu_percent,
            "memory_mb": p.memory_mb,
        }
        for p in list_processes(name_filter)
    ]


@server.tool()
@surface_known_errors
def get_recent_git_commits(repo_path: str, limit: int = 20) -> list[dict]:
    """Lists the most recent commits in a git repo, newest first."""
    commits = get_recent_commits(Path(repo_path), limit)
    return [
        {"sha": c.sha, "author": c.author, "date": c.date, "message": c.message} for c in commits
    ]


@server.tool()
@surface_known_errors
def run_repo_tests(
    repo_path: str, command: str, timeout_seconds: float = DEFAULT_TEST_TIMEOUT_SECONDS
) -> dict:
    """Runs a test command (e.g. 'pytest -q', 'npm test') in a repo directory and reports the
    outcome. Runs the given command directly -- no shell is invoked."""
    result = run_tests(Path(repo_path), command, timeout_seconds)
    return {
        "command": result.command,
        "exit_code": result.exit_code,
        "passed": result.passed,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


@server.tool()
@surface_known_errors
def tail_log_file(path: str, lines: int = 100) -> list[str]:
    """Returns the last N lines of a log file. `path` is relative to the server's configured
    log directory and cannot escape it."""
    return tail_log(Path(LOG_ALLOWED_DIR), path, lines)


if __name__ == "__main__":
    server.run()
