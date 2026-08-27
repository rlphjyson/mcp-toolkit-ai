from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import TypeVar

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from flutter_project_intelligence.dart_scanner import Symbol
from flutter_project_intelligence.project_index import ProjectIndex, build_project_index
from flutter_project_intelligence.project_registry import ProjectRegistry

server = MCPServer(
    "flutter-project-intelligence",
    instructions=(
        "Navigates a Flutter/Dart codebase's structure -- widgets, BLoC/Riverpod state, routes, "
        "repositories/use-cases, API clients, and the project's own package dependencies -- via "
        "heuristic regex parsing over .dart source, no live Dart analyzer required. Call "
        "index_project once per project before using the other tools."
    ),
)

_registry = ProjectRegistry()

T = TypeVar("T")

# See dev_environment/server.py and issue_tracker/server.py for why this exists: MCPServer
# redacts a plain exception's message from the caller by default and only preserves a
# deliberately-raised ToolError's -- this surfaces safe, specific validation error text (unknown
# project_id, missing pubspec.yaml/lib/, unknown file path) instead of a generic one.
KNOWN_SAFE_ERRORS = (ValueError,)


def surface_known_errors(fn: Callable[..., T]) -> Callable[..., T]:
    @wraps(fn)
    def wrapper(*args: object, **kwargs: object) -> T:
        try:
            return fn(*args, **kwargs)
        except KNOWN_SAFE_ERRORS as exc:
            raise ToolError(str(exc)) from exc

    return wrapper


def _all_symbols(index: ProjectIndex) -> list[Symbol]:
    return [symbol for scan in index.files.values() for symbol in scan.symbols]


@server.tool()
@surface_known_errors
def index_project(project_path: str) -> dict:
    """Scans a Flutter project's pubspec.yaml and lib/ directory, building an in-memory index of
    its widgets, state management, routes, repositories/use-cases, and API clients. Call this
    before any other tool. Safe to call again on the same path to pick up source changes."""
    resolved = Path(project_path).resolve()
    index = build_project_index(resolved)
    _registry.put(index)

    symbols = _all_symbols(index)
    routes = [route for scan in index.files.values() for route in scan.routes]
    return {
        "project_id": index.project_id,
        "package_name": index.package_name,
        "dart_files": len(index.files),
        "widgets": sum(1 for s in symbols if s.kind == "widget"),
        "state_management": sum(1 for s in symbols if s.kind == "state_management"),
        "routes": len(routes),
        "repositories": sum(1 for s in symbols if s.kind in ("repository", "use_case")),
        "api_clients": sum(1 for s in symbols if s.kind == "api_client"),
    }


@server.tool()
@surface_known_errors
def find_symbol(project_id: str, name: str) -> list[dict]:
    """Case-insensitive substring search by name across every classified top-level class,
    function, and provider variable in an indexed project."""
    index = _registry.get(project_id)
    needle = name.lower()
    matches = [s for s in _all_symbols(index) if needle in s.name.lower()]
    matches.sort(key=lambda s: (s.file, s.line, s.name))
    return [{"name": s.name, "kind": s.kind, "file": s.file, "line": s.line} for s in matches]


@server.tool()
@surface_known_errors
def list_widgets(project_id: str) -> list[dict]:
    """Every StatelessWidget/StatefulWidget/ConsumerWidget/HookWidget (and their Consumer/Hook
    variants) subclass in an indexed project."""
    index = _registry.get(project_id)
    widgets = sorted(
        (s for s in _all_symbols(index) if s.kind == "widget"), key=lambda s: (s.file, s.line)
    )
    return [
        {"name": s.name, "file": s.file, "line": s.line, "base_class": s.base_class}
        for s in widgets
    ]


@server.tool()
@surface_known_errors
def list_state_management(project_id: str) -> list[dict]:
    """Every Bloc, Cubit, and Riverpod StateNotifier/provider (class-based or code-gen function)
    in an indexed project."""
    index = _registry.get(project_id)
    items = sorted(
        (s for s in _all_symbols(index) if s.kind == "state_management"),
        key=lambda s: (s.file, s.line),
    )
    return [{"name": s.name, "kind": s.state_kind, "file": s.file, "line": s.line} for s in items]


@server.tool()
@surface_known_errors
def list_routes(project_id: str) -> list[dict]:
    """Every route declared in an indexed project, from GoRouter's `GoRoute(path: ...)` entries
    and legacy `MaterialApp.routes` named-route tables."""
    index = _registry.get(project_id)
    routes = sorted(
        (route for scan in index.files.values() for route in scan.routes),
        key=lambda r: (r.file, r.line),
    )
    return [
        {"path": r.path, "file": r.file, "line": r.line, "source": r.source} for r in routes
    ]


@server.tool()
@surface_known_errors
def list_repositories(project_id: str) -> list[dict]:
    """Every *Repository/*RepositoryImpl and *UseCase (or single-`call()`-method) class in an
    indexed project."""
    index = _registry.get(project_id)
    items = sorted(
        (s for s in _all_symbols(index) if s.kind in ("repository", "use_case")),
        key=lambda s: (s.file, s.line),
    )
    return [{"name": s.name, "file": s.file, "line": s.line, "kind": s.kind} for s in items]


@server.tool()
@surface_known_errors
def list_api_clients(project_id: str) -> list[dict]:
    """Every *ApiClient/*Api class, and any other class using Dio() or http.Client() directly,
    in an indexed project."""
    index = _registry.get(project_id)
    items = sorted(
        (s for s in _all_symbols(index) if s.kind == "api_client"), key=lambda s: (s.file, s.line)
    )
    return [{"name": s.name, "file": s.file, "line": s.line} for s in items]


@server.tool()
@surface_known_errors
def get_file_dependencies(project_id: str, file_path: str) -> dict:
    """One file's internal import graph edges: files it imports and files that import it. Only
    covers imports resolvable within the project itself (relative and this project's own
    `package:` imports) -- external packages and dart: imports are excluded. file_path is
    relative to the project root."""
    index = _registry.get(project_id)
    normalized = file_path.replace("\\", "/").lstrip("/")
    if normalized not in index.files:
        raise ValueError(f"'{file_path}' is not a file in this indexed project.")
    return {
        "file": normalized,
        "imports": sorted(index.import_graph.get(normalized, [])),
        "imported_by": sorted(index.reverse_import_graph.get(normalized, [])),
    }


@server.tool()
@surface_known_errors
def get_project_dependencies(project_id: str) -> dict:
    """The indexed project's own pubspec.yaml metadata: package name, Flutter/Dart SDK
    constraint, and declared dependencies/dev_dependencies with their version constraints."""
    index = _registry.get(project_id)
    return {
        "package_name": index.package_name,
        "flutter_sdk_constraint": index.flutter_sdk_constraint,
        "dependencies": index.dependencies,
        "dev_dependencies": index.dev_dependencies,
    }


if __name__ == "__main__":
    server.run()
