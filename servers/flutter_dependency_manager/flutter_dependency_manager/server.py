import os
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import TypeVar

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from flutter_dependency_manager.pub_dev_client import (
    FakePubDevClient,
    PubDevClient,
    RealPubDevClient,
    _to_package_info,
)
from flutter_dependency_manager.pubspec_parser import parse_pubspec
from flutter_dependency_manager.unused_deps import find_unused_dependencies as _find_unused_dependencies

server = MCPServer(
    "flutter-dependency-manager",
    instructions=(
        "Analyzes a Flutter project's pubspec.yaml against pub.dev to find outdated and "
        "discontinued packages, and scans lib/**/*.dart imports to find declared-but-unused "
        "dependencies. `project_path` arguments are the root of a Flutter project (the "
        "directory containing pubspec.yaml)."
    ),
)

T = TypeVar("T")

# See issue_tracker/server.py for why this exists: MCPServer redacts a plain exception's message
# from the caller by default and only preserves a deliberately-raised ToolError's -- this
# surfaces validation and pub.dev lookup errors (missing pubspec.yaml, malformed pubspec.yaml,
# unknown package name) instead of a generic one.
KNOWN_SAFE_ERRORS = (ValueError, FileNotFoundError, httpx.HTTPStatusError)


def surface_known_errors(fn: Callable[..., T]) -> Callable[..., T]:
    @wraps(fn)
    def wrapper(*args: object, **kwargs: object) -> T:
        try:
            return fn(*args, **kwargs)
        except KNOWN_SAFE_ERRORS as exc:
            raise ToolError(str(exc)) from exc

    return wrapper


def _client() -> PubDevClient:
    if os.environ.get("FLUTTER_DEPENDENCY_MANAGER_FAKE_PUBDEV"):
        return FakePubDevClient()
    return RealPubDevClient()


def _pubspec(project_path: str) -> dict:
    return parse_pubspec(Path(project_path) / "pubspec.yaml")


@server.tool()
@surface_known_errors
def list_dependencies(project_path: str) -> dict:
    """Lists a Flutter project's declared dependencies and dev_dependencies from pubspec.yaml."""
    pubspec = _pubspec(project_path)
    return {
        "name": pubspec["name"],
        "dependencies": [{"name": n, "constraint": c} for n, c in pubspec["dependencies"].items()],
        "dev_dependencies": [{"name": n, "constraint": c} for n, c in pubspec["dev_dependencies"].items()],
    }


@server.tool()
@surface_known_errors
def check_outdated(project_path: str) -> list[dict]:
    """Checks each hosted dependency against pub.dev for a newer version. Git/path/sdk
    dependencies are reported with a null latest_version rather than queried. A genuinely
    unknown (typo'd) hosted package name raises an error naming the package."""
    pubspec = _pubspec(project_path)
    client = _client()
    results = []

    for name, constraint in pubspec["dependencies"].items():
        if constraint.startswith(("git:", "path:", "sdk:")):
            results.append(
                {"name": name, "current_constraint": constraint, "latest_version": None, "is_outdated": False}
            )
            continue

        try:
            raw = client.get_package_info(name)
        except ValueError as exc:
            raise ValueError(f"Unknown pub.dev package: {name}") from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise ValueError(f"Unknown pub.dev package: {name}") from exc
            results.append(
                {"name": name, "current_constraint": constraint, "latest_version": None, "is_outdated": False}
            )
            continue
        except httpx.HTTPError:
            results.append(
                {"name": name, "current_constraint": constraint, "latest_version": None, "is_outdated": False}
            )
            continue

        info = _to_package_info(name, constraint, raw)
        results.append(
            {
                "name": info.name,
                "current_constraint": info.current_constraint,
                "latest_version": info.latest_version,
                "is_outdated": info.is_outdated,
            }
        )

    return results


@server.tool()
@surface_known_errors
def check_discontinued_packages(project_path: str) -> list[dict]:
    """Flags hosted dependencies pub.dev marks as discontinued, with their replacement if any."""
    pubspec = _pubspec(project_path)
    client = _client()
    results = []

    for name, constraint in pubspec["dependencies"].items():
        if constraint.startswith(("git:", "path:", "sdk:")):
            continue

        try:
            raw = client.get_package_info(name)
        except ValueError:
            continue
        except httpx.HTTPError:
            continue

        info = _to_package_info(name, constraint, raw)
        if info.is_discontinued:
            results.append(
                {
                    "name": info.name,
                    "is_discontinued": info.is_discontinued,
                    "replaced_by": info.replaced_by,
                }
            )

    return results


@server.tool()
@surface_known_errors
def find_unused_dependencies(project_path: str) -> list[str]:
    """Declared dependencies never imported (`package:<name>/...`) anywhere under lib/."""
    return _find_unused_dependencies(Path(project_path))


if __name__ == "__main__":
    server.run()
