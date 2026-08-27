import subprocess
from datetime import UTC, datetime
from pathlib import Path

from flutter_crash_analyzer.config import GIT_TIMEOUT_SECONDS


def blame_line(repo_path: Path, file_path: str, line: int) -> dict | None:
    try:
        process = subprocess.run(
            ["git", "blame", "-L", f"{line},{line}", "--porcelain", "--", file_path],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
            check=True,
        )
    except (subprocess.CalledProcessError, OSError):
        return None

    return _parse_porcelain(process.stdout)


def _parse_porcelain(output: str) -> dict | None:
    lines = output.splitlines()
    if not lines:
        return None

    header = lines[0].split()
    if not header:
        return None

    result: dict = {"sha": header[0], "author": None, "date": None, "summary": None}
    for line in lines[1:]:
        if line.startswith("author "):
            result["author"] = line.removeprefix("author ")
        elif line.startswith("author-time "):
            timestamp = int(line.removeprefix("author-time "))
            result["date"] = datetime.fromtimestamp(timestamp, tz=UTC).isoformat()
        elif line.startswith("summary "):
            result["summary"] = line.removeprefix("summary ")
        elif line.startswith("\t"):
            break

    return result
