import hashlib
import json
from pathlib import Path

from codebase_intelligence.config import REGISTRY_PATH


def repo_id_for(repo_path: Path) -> str:
    """Deterministic short id for a repo path -- re-indexing the same path always reuses the
    same id, making index_repository idempotent."""
    return hashlib.sha256(str(repo_path.resolve()).encode()).hexdigest()[:12]


class RepoRegistry:
    """Persists the repo_id -> absolute path mapping to a small JSON file so a server restart
    doesn't lose track of what's already been indexed in Chroma."""

    def __init__(self, path: Path = REGISTRY_PATH) -> None:
        self._path = path
        self._repos: dict[str, str] = self._load()

    def _load(self) -> dict[str, str]:
        if not self._path.exists():
            return {}
        return json.loads(self._path.read_text())

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._repos, indent=2))

    def register(self, repo_path: Path) -> str:
        repo_id = repo_id_for(repo_path)
        self._repos[repo_id] = str(repo_path.resolve())
        self._save()
        return repo_id

    def resolve(self, repo_id: str) -> Path | None:
        path = self._repos.get(repo_id)
        return Path(path) if path else None
