import re
from collections import deque
from pathlib import Path


def _validate_file(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"No such log file: {path}")
    if not resolved.is_file():
        raise ValueError(f"Not a file: {path}")
    return resolved


def tail_lines(path: Path, lines: int) -> list[str]:
    resolved = _validate_file(path)
    with resolved.open("r", encoding="utf-8", errors="replace") as f:
        return [line.rstrip("\n") for line in deque(f, maxlen=lines)]


def search_log(path: Path, pattern: str, max_matches: int = 50) -> list[dict]:
    resolved = _validate_file(path)
    try:
        regex = re.compile(pattern)
    except re.error as exc:
        raise ValueError(f"Invalid regex pattern: {exc}") from exc

    matches = []
    with resolved.open("r", encoding="utf-8", errors="replace") as f:
        for line_number, raw_line in enumerate(f, start=1):
            line = raw_line.rstrip("\n")
            if regex.search(line):
                matches.append({"line_number": line_number, "line": line})
                if len(matches) >= max_matches:
                    break
    return matches
