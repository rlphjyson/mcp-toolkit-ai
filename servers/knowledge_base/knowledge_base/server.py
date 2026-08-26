from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import TypeVar

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ResourceError, ToolError

from knowledge_base.config import VAULT_DIR
from knowledge_base.notes import create_note as _create_note
from knowledge_base.notes import get_backlinks as _get_backlinks
from knowledge_base.notes import get_note as _get_note
from knowledge_base.notes import search_notes as _search_notes

server = MCPServer(
    "knowledge-base",
    instructions=(
        "Personal knowledge base over a local Markdown vault. Notes link to each other with "
        f"[[wikilink]] syntax. The vault is at {VAULT_DIR}."
    ),
)

T = TypeVar("T")

KNOWN_SAFE_ERRORS = (ValueError,)


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


def _vault() -> Path:
    return Path(VAULT_DIR)


@server.tool()
@surface_tool_errors
def search_notes(query: str) -> list[dict]:
    """Case-insensitive search over note titles and content."""
    return [{"path": n.path, "title": n.title} for n in _search_notes(_vault(), query)]


@server.tool()
@surface_tool_errors
def create_note(title: str, content: str = "") -> dict:
    """Creates a new note. The filename is derived from the title (and de-duplicated if it
    collides with an existing note)."""
    note = _create_note(_vault(), title, content)
    return {"path": note.path, "title": note.title}


@server.tool()
@surface_tool_errors
def get_backlinks(path: str) -> list[dict]:
    """Finds every note that links to the given note via [[wikilink]] (matched against the
    target note's title or filename)."""
    return [{"path": n.path, "title": n.title} for n in _get_backlinks(_vault(), path)]


@server.resource("note://{+path}")
@surface_resource_errors
def read_note(path: str) -> str:
    """Raw Markdown content of one note."""
    return _get_note(_vault(), path).content


if __name__ == "__main__":
    server.run()
