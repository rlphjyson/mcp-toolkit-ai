from collections import deque
from pathlib import Path


def tail_log(allowed_dir: Path, relative_path: str, lines: int) -> list[str]:
    allowed_dir = allowed_dir.resolve()
    target = (allowed_dir / relative_path).resolve()

    if not target.is_relative_to(allowed_dir):
        raise ValueError(f"Path escapes the allowed log directory: {relative_path}")
    if not target.is_file():
        raise ValueError(f"No such log file: {relative_path}")

    with target.open("r", encoding="utf-8", errors="replace") as f:
        return [line.rstrip("\n") for line in deque(f, maxlen=lines)]
