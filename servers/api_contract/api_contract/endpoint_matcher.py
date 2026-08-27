import re
from pathlib import Path

_CALL_METHODS = ("get", "post", "put", "patch", "delete")
_CALL_LITERAL_RE = re.compile(
    r"\.(?:" + "|".join(_CALL_METHODS) + r")\s*\(\s*(['\"])((?:\\.|(?!\1).)*)\1"
)

_OPENAPI_PARAM_RE = re.compile(r"\{[^{}]+\}")
_DART_BRACED_INTERP_RE = re.compile(r"\$\{[^{}]+\}")
_DART_BARE_INTERP_RE = re.compile(r"\$[A-Za-z_]\w*")


def find_called_endpoint_paths(project_path: Path) -> set[str]:
    """Regex-scans lib/**/*.dart for string literals that look like API paths (start with '/')
    passed as the first argument to a `.get(`/`.post(`/`.put(`/`.patch(`/`.delete(` call --
    typical Dio or http.Client usage -- and returns the raw literal strings found.

    Limitation: this can't resolve Dart string interpolation to a concrete value, so a spec
    path template like `/users/{id}` will not literally match a call site written with
    interpolation like `/users/$userId`. Use `_normalize_path_for_matching` on both sides
    (spec path and called path) to get useful matches despite this.
    """
    paths: set[str] = set()
    for dart_file in project_path.glob("lib/**/*.dart"):
        source = dart_file.read_text(encoding="utf-8", errors="ignore")
        for match in _CALL_LITERAL_RE.finditer(source):
            literal = match.group(2)
            if literal.startswith("/"):
                paths.add(literal)
    return paths


def _normalize_path_for_matching(path: str) -> str:
    """Collapses both OpenAPI `{param}` segments and Dart `$var`/`${var}` interpolation
    segments to a single wildcard token `*`, so a spec path like `/users/{id}` and a call site
    written as `/users/$userId` normalize to the same `/users/*` and can be matched despite
    neither being resolved to a concrete literal value."""
    # Dart's `${...}` must be collapsed before the generic `{...}` pass below, otherwise that
    # pass matches the inner `{...}` first and leaves a stray `$*` behind.
    normalized = _DART_BRACED_INTERP_RE.sub("*", path)
    normalized = _DART_BARE_INTERP_RE.sub("*", normalized)
    normalized = _OPENAPI_PARAM_RE.sub("*", normalized)
    return normalized
