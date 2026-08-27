from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flutter_project_intelligence.project_index import ProjectIndex


def project_id_for(project_root: Path) -> str:
    """Deterministic short id for a project path -- re-indexing the same path always reuses the
    same id, making index_project idempotent."""
    return hashlib.sha256(str(project_root.resolve()).encode()).hexdigest()[:12]


class ProjectRegistry:
    """In-memory project_id -> parsed ProjectIndex store. Deliberately not persisted to disk
    (unlike codebase_intelligence's RepoRegistry): the index itself, not just the path mapping,
    lives here, and re-scanning a project is cheap enough that losing it on restart is fine."""

    def __init__(self) -> None:
        self._projects: dict[str, ProjectIndex] = {}

    def put(self, index: ProjectIndex) -> None:
        self._projects[index.project_id] = index

    def get(self, project_id: str) -> ProjectIndex:
        index = self._projects.get(project_id)
        if index is None:
            raise ValueError(f"Unknown project_id '{project_id}'. Call index_project first.")
        return index
