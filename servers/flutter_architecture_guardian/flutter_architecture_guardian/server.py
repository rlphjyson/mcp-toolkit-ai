from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import TypeVar

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from flutter_architecture_guardian.clean_architecture_rules import check_clean_architecture
from flutter_architecture_guardian.config import PUBLIC_API_MARKERS
from flutter_architecture_guardian.feature_first_rules import check_feature_first
from flutter_architecture_guardian.import_graph import build_import_graph
from flutter_architecture_guardian.layer_classifier import classify_clean_layer, classify_feature
from flutter_architecture_guardian.violations import Violation

server = MCPServer(
    "flutter-architecture-guardian",
    instructions=(
        "Static analysis of a Flutter project's lib/ import graph for Clean Architecture / "
        "feature-first layering violations. Pass style='clean' for a presentation/domain/data "
        "layered project, or style='feature_first' for a lib/features/<name>/ project. No "
        "network access and no Flutter SDK required -- pure source scanning."
    ),
)

T = TypeVar("T")

STYLES = ("clean", "feature_first")

# See dev_environment/server.py and codebase_intelligence/server.py for why this exists: MCPServer
# redacts a plain exception's message from the caller by default and only preserves a
# deliberately-raised ToolError's -- this surfaces safe, specific validation error text (bad
# style, missing pubspec.yaml/lib dir) instead of a generic one.
KNOWN_SAFE_ERRORS = (ValueError,)


def surface_known_errors(fn: Callable[..., T]) -> Callable[..., T]:
    @wraps(fn)
    def wrapper(*args: object, **kwargs: object) -> T:
        try:
            return fn(*args, **kwargs)
        except KNOWN_SAFE_ERRORS as exc:
            raise ToolError(str(exc)) from exc

    return wrapper


def _validate_style(style: str) -> None:
    if style not in STYLES:
        raise ValueError(f"Unknown style '{style}'. Must be one of: {', '.join(STYLES)}.")


def _find_violations(project_path: str, style: str) -> tuple[dict[str, list[str]], list[Violation]]:
    _validate_style(style)
    graph = build_import_graph(Path(project_path))
    if style == "clean":
        violations = check_clean_architecture(graph, classify_clean_layer)
    else:
        violations = check_feature_first(graph, classify_feature, PUBLIC_API_MARKERS)
    return graph, violations


def _violation_dict(violation: Violation) -> dict:
    return {
        "file": violation.file,
        "imported_file": violation.imported_file,
        "rule": violation.rule,
        "message": violation.message,
    }


@server.tool()
@surface_known_errors
def analyze_architecture(project_path: str, style: str = "clean") -> dict:
    """Scans a Flutter project's lib/ tree and reports import-graph layering violations for the
    given architecture style ("clean" or "feature_first")."""
    graph, violations = _find_violations(project_path, style)
    return {
        "style": style,
        "files_scanned": len(graph),
        "violation_count": len(violations),
        "violations": [_violation_dict(v) for v in violations],
    }


@server.tool()
@surface_known_errors
def list_layer_violations(project_path: str, style: str = "clean") -> list[dict]:
    """Just the list of layering violations for a Flutter project, without the surrounding
    summary -- a convenience over analyze_architecture for callers that only want the list."""
    _, violations = _find_violations(project_path, style)
    return [_violation_dict(v) for v in violations]


@server.tool()
@surface_known_errors
def get_project_layer_summary(project_path: str, style: str = "clean") -> dict:
    """Counts of .dart files per detected layer ("clean" style: presentation/domain/data) or
    per feature ("feature_first" style), plus an "unclassified" count for files matching
    neither."""
    _validate_style(style)
    graph = build_import_graph(Path(project_path))
    classify = classify_clean_layer if style == "clean" else classify_feature

    counts: dict[str, int] = {}
    for file in graph:
        key = classify(file) or "unclassified"
        counts[key] = counts.get(key, 0) + 1
    return counts


if __name__ == "__main__":
    server.run()
