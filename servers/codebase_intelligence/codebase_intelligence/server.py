import subprocess
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import TypeVar

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ResourceError, ToolError

from codebase_intelligence.chunking import chunk_repository
from codebase_intelligence.embeddings import get_embedder
from codebase_intelligence.git_history import get_file_history as _get_file_history
from codebase_intelligence.github_prs import RealGitHubClient
from codebase_intelligence.index_store import get_index_store
from codebase_intelligence.related_prs import find_related_prs
from codebase_intelligence.repo_registry import RepoRegistry

server = MCPServer(
    "codebase-intelligence",
    instructions=(
        "Semantic code search, file history, and related-PR lookup over an indexed git repo. "
        "Call index_repository once per repo before using the other tools."
    ),
)

_registry = RepoRegistry()

T = TypeVar("T")

# By default, an MCPServer tool/resource that raises anything other than its own ToolError/
# ResourceError is treated as an unexpected crash: the message is logged server-side but
# replaced with a generic one for the caller (confirmed by reading mcp.server.mcpserver.tools.
# base's exception handling -- a deliberate, sensible security default against leaking
# internals). This module deliberately raises plain ValueError/CalledProcessError/
# HTTPStatusError for conditions that are entirely safe and useful to show the caller (unknown
# repo_id, a path outside the repo, git or GitHub API failures) -- these decorators are what
# actually surface those messages instead of a generic one.
KNOWN_SAFE_ERRORS = (ValueError, subprocess.CalledProcessError, httpx.HTTPStatusError)


def surface_tool_errors(fn: Callable[..., T]) -> Callable[..., T]:
    @wraps(fn)
    def wrapper(*args: object, **kwargs: object) -> T:
        try:
            return fn(*args, **kwargs)
        except KNOWN_SAFE_ERRORS as exc:
            raise ToolError(str(exc)) from exc

    return wrapper


def surface_resource_errors(fn: Callable[..., T]) -> Callable[..., T]:
    @wraps(fn)
    def wrapper(*args: object, **kwargs: object) -> T:
        try:
            return fn(*args, **kwargs)
        except KNOWN_SAFE_ERRORS as exc:
            raise ResourceError(str(exc)) from exc

    return wrapper


def _resolve_repo(repo_id: str) -> Path:
    repo_path = _registry.resolve(repo_id)
    if repo_path is None:
        raise ValueError(f"Unknown repo_id '{repo_id}'. Call index_repository first.")
    return repo_path


@server.tool()
@surface_tool_errors
def index_repository(repo_path: str) -> dict:
    """Indexes a local git repository for semantic search. Safe to call again on the same path
    to pick up file changes -- re-indexing replaces that repo's previous index."""
    resolved = Path(repo_path).resolve()
    if not resolved.is_dir():
        raise ValueError(f"'{repo_path}' is not a directory.")

    repo_id = _registry.register(resolved)
    chunks = chunk_repository(resolved)

    if chunks:
        embeddings = get_embedder().embed([c.text for c in chunks])
        get_index_store().index_repo(repo_id, chunks, embeddings)
    else:
        get_index_store().index_repo(repo_id, [], [])

    indexed_files = len({c.relative_path for c in chunks})
    return {"repo_id": repo_id, "indexed_files": indexed_files, "chunks": len(chunks)}


@server.tool()
@surface_tool_errors
def search_code(repo_id: str, query: str, top_k: int = 5) -> list[dict]:
    """Semantic search over a previously indexed repo's files."""
    _resolve_repo(repo_id)  # validates repo_id up front, same error either way
    query_embedding = get_embedder().embed([query])[0]
    hits = get_index_store().search(repo_id, query_embedding, top_k)
    return [
        {"file": h.file, "chunk_index": h.chunk_index, "text": h.text, "distance": h.distance}
        for h in hits
    ]


@server.tool()
@surface_tool_errors
def get_file_history(repo_id: str, path: str, limit: int = 10) -> list[dict]:
    """Commit history for one file in an indexed repo (author, date, message)."""
    repo_path = _resolve_repo(repo_id)
    commits = _get_file_history(repo_path, path, limit)
    return [
        {"sha": c.sha, "author": c.author, "date": c.date, "message": c.message} for c in commits
    ]


@server.tool()
@surface_tool_errors
def get_related_prs(repo_id: str, path: str, github_repo: str, limit: int = 5) -> list[dict]:
    """Pull requests that touched a file, found by cross-referencing its commit history against
    GitHub's 'PRs associated with a commit' API. github_repo is 'owner/name'."""
    repo_path = _resolve_repo(repo_id)
    commits = _get_file_history(repo_path, path, limit=20)
    prs = find_related_prs(commits, github_repo, RealGitHubClient(), limit=limit)
    return [{"number": pr.number, "title": pr.title, "url": pr.url} for pr in prs]


@server.resource("code://{repo_id}/{+path}")
@surface_resource_errors
def read_file(repo_id: str, path: str) -> str:
    """Raw content of one file in an indexed repo."""
    repo_path = _resolve_repo(repo_id)
    file_path = (repo_path / path).resolve()
    if repo_path not in file_path.parents and file_path != repo_path:
        raise ValueError("Resolved path escapes the repo directory.")
    if not file_path.is_file():
        raise ValueError(f"'{path}' is not a file in this repo.")
    return file_path.read_text(encoding="utf-8", errors="ignore")


if __name__ == "__main__":
    server.run()
