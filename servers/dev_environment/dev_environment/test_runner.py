import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class RunTimeoutError(Exception):
    pass


@dataclass
class TestRunResult:
    command: str
    exit_code: int
    passed: bool
    stdout: str
    stderr: str


def _split_command(command: str) -> list[str]:
    # shlex.split's default posix mode treats backslash as an escape character, which mangles
    # Windows paths (e.g. "C:\Users\..." loses its backslashes). posix=False preserves them but
    # leaves surrounding quote characters on quoted tokens (e.g. '"print(1)"'), so strip those
    # off explicitly -- this is the one split that behaves correctly on both platforms.
    tokens = shlex.split(command, posix=False)
    stripped = []
    for token in tokens:
        if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'":
            token = token[1:-1]
        stripped.append(token)
    return stripped


def run_tests(repo_path: Path, command: str, timeout_seconds: float) -> TestRunResult:
    args = _split_command(command)
    if not args:
        raise ValueError("No command given.")

    # On Windows, subprocess.run does not follow PATHEXT resolution for a bare command name the
    # way a real shell does (e.g. "pytest" or "npm" are often .exe/.cmd shims) -- resolve the
    # executable explicitly so commands that work in a terminal also work here.
    resolved = shutil.which(args[0])
    if resolved:
        args[0] = resolved

    try:
        process = subprocess.run(
            args,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise RunTimeoutError(
            f"Test command timed out after {timeout_seconds}s: {command}"
        ) from exc
    except FileNotFoundError as exc:
        raise ValueError(f"Command not found: {args[0]}") from exc

    return TestRunResult(
        command=command,
        exit_code=process.returncode,
        passed=process.returncode == 0,
        stdout=process.stdout,
        stderr=process.stderr,
    )
