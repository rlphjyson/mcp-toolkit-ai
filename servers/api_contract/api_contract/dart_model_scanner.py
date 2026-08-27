import re
from pathlib import Path

# `final Type fieldName;` / `final Type? fieldName;` field declarations. The type portion is
# matched non-greedily so it stops at the first whitespace-then-identifier-then-semicolon split
# that makes the whole match valid, which tolerates generics like `final List<String> tags;`.
_FINAL_FIELD_RE = re.compile(r"final\s+[\w<>,\.\s\?]+?\s+(\w+)\s*;")

# `required this.fieldName,` (freezed/standard named-constructor params) and plain
# `this.fieldName,` / `this.fieldName)` for positional or non-required params.
_CONSTRUCTOR_FIELD_RE = re.compile(r"(?:required\s+)?this\.(\w+)\s*[,)}]")

_FACTORY_HEADER_RE = re.compile(r"factory\s+\w+\s*\(")

# Freezed-style factory constructor params, e.g. `required String id,` / `double? price,` --
# these declare fields directly by name (no `this.` prefix), unlike a plain data class.
_FACTORY_PARAM_RE = re.compile(r"(?:required\s+)?[^,(){}]+?\s+(\w+)\s*[,)]")


def find_dart_model_fields(project_path: Path, class_name: str) -> list[str] | None:
    """Regex-scans lib/**/*.dart for a Dart model class and extracts its declared field names,
    from `final Type fieldName;` declarations and `this.fieldName`/`required this.fieldName`
    constructor params (covers both plain data classes and freezed-style `@freezed`/`factory`
    classes, since freezed classes declare fields the same way in their generated/abstract
    class body). Tries `class_name` first, then `<class_name>Model` and `<class_name>Dto` as
    fallbacks. This is a tolerant brace-matched block extraction, not a full Dart parser.
    Returns None if no matching class is found anywhere under lib/."""
    for candidate in (class_name, f"{class_name}Model", f"{class_name}Dto"):
        for dart_file in sorted(project_path.glob("lib/**/*.dart")):
            source = dart_file.read_text(encoding="utf-8", errors="ignore")
            body = _extract_class_body(source, candidate)
            if body is not None:
                return _extract_fields(body)
    return None


def _extract_class_body(source: str, class_name: str) -> str | None:
    header_re = re.compile(r"class\s+" + re.escape(class_name) + r"\b[^{]*\{")
    match = header_re.search(source)
    if match is None:
        return None

    depth = 1
    pos = match.end()
    while pos < len(source) and depth > 0:
        if source[pos] == "{":
            depth += 1
        elif source[pos] == "}":
            depth -= 1
        pos += 1
    return source[match.end() : pos - 1]


def _extract_fields(class_body: str) -> list[str]:
    fields = {m.group(1) for m in _FINAL_FIELD_RE.finditer(class_body)}
    fields.update(m.group(1) for m in _CONSTRUCTOR_FIELD_RE.finditer(class_body))

    factory_params = _extract_factory_params(class_body)
    if factory_params is not None:
        fields.update(m.group(1) for m in _FACTORY_PARAM_RE.finditer(factory_params))

    return sorted(fields)


def _extract_factory_params(class_body: str) -> str | None:
    match = _FACTORY_HEADER_RE.search(class_body)
    if match is None:
        return None

    depth = 1
    pos = match.end()
    while pos < len(class_body) and depth > 0:
        if class_body[pos] == "(":
            depth += 1
        elif class_body[pos] == ")":
            depth -= 1
        pos += 1
    return class_body[match.end() : pos - 1]
