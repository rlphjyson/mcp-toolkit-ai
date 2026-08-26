import subprocess
from dataclasses import dataclass
from pathlib import Path

RECORD_SEP = "\x1e"
FIELD_SEP = "\x1f"
LOG_FORMAT = FIELD_SEP.join(["%H", "%an", "%ad", "%s"]) + RECORD_SEP


@dataclass
class CommitInfo:
    sha: str
    author: str
    date: str
    message: str


def get_recent_commits(repo_path: Path, limit: int = 20) -> list[CommitInfo]:
    process = subprocess.run(
        ["git", "log", f"-n{limit}", f"--pretty=format:{LOG_FORMAT}", "--date=iso-strict"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return _parse_log(process.stdout)


def _parse_log(output: str) -> list[CommitInfo]:
    commits = []
    for record in output.split(RECORD_SEP):
        record = record.strip()
        if not record:
            continue
        sha, author, date, message = record.split(FIELD_SEP)
        commits.append(CommitInfo(sha=sha, author=author, date=date, message=message))
    return commits
