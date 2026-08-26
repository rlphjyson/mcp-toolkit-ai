from dataclasses import dataclass
from pathlib import Path

from codebase_intelligence.config import (
    INDEXABLE_EXTENSIONS,
    MAX_FILE_SIZE_BYTES,
    SKIP_DIR_NAMES,
)


@dataclass
class FileChunk:
    relative_path: str
    chunk_index: int
    text: str


def discover_files(repo_path: Path) -> list[Path]:
    files = []
    for path in repo_path.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        if path.suffix not in INDEXABLE_EXTENSIONS:
            continue
        try:
            if path.stat().st_size > MAX_FILE_SIZE_BYTES:
                continue
        except OSError:
            continue
        files.append(path)
    return files


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 150) -> list[str]:
    """Splits text into overlapping, whitespace-normalized character windows.

    Character-based (not token-based) to stay dependency-free, same approach as docuchat-ai.
    """
    normalized = " ".join(text.split())
    if not normalized:
        return []
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be greater than overlap")

    chunks = []
    start = 0
    while start < len(normalized):
        end = start + chunk_size
        chunks.append(normalized[start:end])
        if end >= len(normalized):
            break
        start = end - overlap
    return chunks


def chunk_repository(repo_path: Path) -> list[FileChunk]:
    file_chunks = []
    for file_path in discover_files(repo_path):
        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        relative_path = str(file_path.relative_to(repo_path)).replace("\\", "/")
        for index, chunk in enumerate(chunk_text(text)):
            file_chunks.append(FileChunk(relative_path=relative_path, chunk_index=index, text=chunk))
    return file_chunks
