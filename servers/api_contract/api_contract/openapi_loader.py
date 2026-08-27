from pathlib import Path

import httpx
import yaml

from api_contract.config import HTTP_TIMEOUT_SECONDS

_HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}


def load_spec(path_or_url: str) -> dict:
    """Loads an OpenAPI 3.x (or Swagger 2.0) spec from a local file path or an http(s) URL.
    Parsed with pyyaml's safe_load, which also parses JSON since JSON is a subset of YAML, so
    this handles both spec formats uniformly."""
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        response = httpx.get(path_or_url, timeout=HTTP_TIMEOUT_SECONDS)
        response.raise_for_status()
        text = response.text
    else:
        text = Path(path_or_url).read_text(encoding="utf-8")

    spec = yaml.safe_load(text)
    if not isinstance(spec, dict) or ("openapi" not in spec and "swagger" not in spec):
        raise ValueError(
            f"'{path_or_url}' does not look like an OpenAPI/Swagger spec (missing top-level "
            "'openapi' or 'swagger' key)."
        )
    return spec


def list_endpoints(spec: dict) -> list[dict]:
    """Every path+method operation in the spec, flattened to one entry per endpoint."""
    endpoints = []
    for path, path_item in (spec.get("paths") or {}).items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in _HTTP_METHODS or not isinstance(operation, dict):
                continue
            endpoints.append(
                {
                    "path": path,
                    "method": method.upper(),
                    "operation_id": operation.get("operationId"),
                    "deprecated": bool(operation.get("deprecated", False)),
                }
            )
    return endpoints


def resolve_schema(spec: dict, schema_name: str) -> dict:
    """Looks up a named schema under components.schemas (OpenAPI 3.x shape)."""
    schemas = (spec.get("components") or {}).get("schemas") or {}
    if schema_name not in schemas:
        raise ValueError(f"Schema '{schema_name}' not found in spec components.schemas.")
    return dict(schemas[schema_name])
