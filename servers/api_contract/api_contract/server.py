from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import TypeVar

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from api_contract.dart_model_scanner import find_dart_model_fields
from api_contract.endpoint_matcher import _normalize_path_for_matching, find_called_endpoint_paths
from api_contract.openapi_loader import list_endpoints as _list_endpoints
from api_contract.openapi_loader import load_spec, resolve_schema
from api_contract.spec_registry import get_spec, register_spec

server = MCPServer(
    "api-contract",
    instructions=(
        "Static comparison of an OpenAPI spec against a Flutter project's Dart models and API "
        "call sites. Call load_openapi_spec once per spec (local file path or http(s) URL) to "
        "get a spec_id, then use the other tools against that spec_id."
    ),
)

T = TypeVar("T")

# See codebase_intelligence/server.py and sql_query/server.py for why this exists: MCPServer
# redacts a plain exception's message from the caller by default and only preserves a
# deliberately-raised ToolError's -- this surfaces safe, specific validation/HTTP error text
# (unknown spec_id, missing schema, unparseable spec, network failure) instead of a generic one.
KNOWN_SAFE_ERRORS = (ValueError, httpx.HTTPStatusError, httpx.HTTPError)


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
def load_openapi_spec(path_or_url: str) -> dict:
    """Loads an OpenAPI 3.x/Swagger 2.0 spec from a local file path or an http(s) URL and
    registers it for the other tools. Returns the spec_id to pass to them."""
    spec = load_spec(path_or_url)
    spec_id = register_spec(spec)
    info = spec.get("info") or {}
    return {
        "spec_id": spec_id,
        "title": info.get("title"),
        "version": info.get("version"),
        "endpoint_count": len(_list_endpoints(spec)),
    }


@server.tool()
@surface_known_errors
def list_endpoints(spec_id: str) -> list[dict]:
    """Lists every path+method endpoint declared in a previously loaded spec."""
    return _list_endpoints(get_spec(spec_id))


@server.tool()
@surface_known_errors
def find_deprecated_endpoints(spec_id: str) -> list[dict]:
    """Lists endpoints in a previously loaded spec that are marked `deprecated: true`."""
    return [e for e in _list_endpoints(get_spec(spec_id)) if e["deprecated"]]


@server.tool()
@surface_known_errors
def compare_model_to_schema(
    spec_id: str, schema_name: str, project_path: str, dart_class_name: str
) -> dict:
    """Compares an OpenAPI component schema's properties against a Dart model class's fields in
    a Flutter project. If the Dart class can't be found, dart_fields is null and both diff
    lists are empty (this is an expected, non-error outcome -- a caller might be probing
    whether a model exists at all)."""
    schema = resolve_schema(get_spec(spec_id), schema_name)
    schema_fields = sorted((schema.get("properties") or {}).keys())

    dart_fields = find_dart_model_fields(Path(project_path), dart_class_name)

    if dart_fields is None:
        return {
            "schema_name": schema_name,
            "dart_class_name": dart_class_name,
            "schema_fields": schema_fields,
            "dart_fields": None,
            "missing_in_dart_model": [],
            "extra_in_dart_model": [],
            "note": f"No Dart class matching '{dart_class_name}' was found under {project_path}/lib.",
        }

    schema_set, dart_set = set(schema_fields), set(dart_fields)
    return {
        "schema_name": schema_name,
        "dart_class_name": dart_class_name,
        "schema_fields": schema_fields,
        "dart_fields": dart_fields,
        "missing_in_dart_model": sorted(schema_set - dart_set),
        "extra_in_dart_model": sorted(dart_set - schema_set),
    }


@server.tool()
@surface_known_errors
def find_uncalled_endpoints(spec_id: str, project_path: str) -> list[dict]:
    """Spec endpoints whose path is never called from the Flutter project's Dart source, after
    normalizing both OpenAPI `{param}` templates and Dart string-interpolation segments to a
    common wildcard so equivalent parameterized paths still match."""
    called = {
        _normalize_path_for_matching(p) for p in find_called_endpoint_paths(Path(project_path))
    }
    return [
        e
        for e in _list_endpoints(get_spec(spec_id))
        if _normalize_path_for_matching(e["path"]) not in called
    ]


if __name__ == "__main__":
    server.run()
