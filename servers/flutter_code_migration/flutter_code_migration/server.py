from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import TypeVar

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from flutter_code_migration import scanner, transformer
from flutter_code_migration.migration_rules import MIGRATIONS

server = MCPServer(
    "flutter-code-migration",
    instructions=(
        "Scans a Flutter project for legacy API/pattern usage and builds a migration plan. Only "
        "'deprecated_widgets' contains genuine 1:1 mechanical renames that can be auto-applied "
        "(e.g. RaisedButton -> ElevatedButton); 'navigator_to_gorouter' and 'bloc_to_riverpod' "
        "are detection/guidance only -- those migrations are semantic, not a mechanical "
        "find/replace, so apply_transformation refuses to run on them."
    ),
)

T = TypeVar("T")

# See dev_environment/server.py for why this exists: MCPServer redacts a plain exception's
# message from the caller by default and only preserves a deliberately-raised ToolError's -- this
# surfaces safe, specific validation/filesystem error text instead of a generic one.
KNOWN_SAFE_ERRORS = (ValueError, FileNotFoundError)


def surface_known_errors(fn: Callable[..., T]) -> Callable[..., T]:
    @wraps(fn)
    def wrapper(*args: object, **kwargs: object) -> T:
        try:
            return fn(*args, **kwargs)
        except KNOWN_SAFE_ERRORS as exc:
            raise ToolError(str(exc)) from exc

    return wrapper


@server.tool()
@surface_known_errors
def list_available_migrations() -> list[dict]:
    """Lists every supported migration, showing how many of its rules are mechanical (a safe,
    auto-applicable find/replace) versus manual_required (detection and guidance only)."""
    return [
        {
            "migration_id": migration_id,
            "rule_count": len(rules),
            "mechanical_rule_count": sum(1 for r in rules if r.replacement is not None),
            "manual_required_rule_count": sum(1 for r in rules if r.replacement is None),
        }
        for migration_id, rules in MIGRATIONS.items()
    ]


@server.tool()
@surface_known_errors
def scan_for_legacy_patterns(project_path: str, migration: str) -> list[dict]:
    """Regex-scans lib/**/*.dart in a Flutter project for every rule of the given migration and
    returns each match's file, line, category, and description."""
    return scanner.scan_for_legacy_patterns(Path(project_path), migration)


@server.tool()
@surface_known_errors
def create_migration_plan(project_path: str, migration: str) -> dict:
    """Scans a Flutter project for a migration's legacy patterns and groups the matches by file,
    with mechanical vs manual_required totals."""
    return scanner.create_migration_plan(Path(project_path), migration)


@server.tool()
@surface_known_errors
def preview_transformation(file_path: str, migration: str) -> dict:
    """Applies only a migration's mechanical (safe, well-defined) rules to a single file
    in-memory and returns the before/after content without writing anything to disk."""
    return transformer.preview_transformation(Path(file_path), migration)


@server.tool()
@surface_known_errors
def apply_transformation(file_path: str, migration: str, dry_run: bool = True) -> dict:
    """Applies a migration's mechanical rules to a single file. With dry_run=True (the default)
    this behaves exactly like preview_transformation and writes nothing. With dry_run=False it
    writes the transformed content back to file_path. Refuses with a clear error if the migration
    has no mechanical rules at all (e.g. navigator_to_gorouter, bloc_to_riverpod)."""
    return transformer.apply_transformation(Path(file_path), migration, dry_run)


if __name__ == "__main__":
    server.run()
