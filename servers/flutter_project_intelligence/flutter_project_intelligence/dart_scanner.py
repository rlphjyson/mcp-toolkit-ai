import re
from dataclasses import dataclass, field
from pathlib import Path

from flutter_project_intelligence.config import MAX_DART_FILE_SIZE_BYTES

WIDGET_BASE_CLASSES = {
    "StatelessWidget",
    "StatefulWidget",
    "ConsumerWidget",
    "ConsumerStatefulWidget",
    "HookWidget",
    "HookConsumerWidget",
}

IMPORT_RE = re.compile(r"""^import\s+['"]([^'"]+)['"]""")
CLASS_LINE_RE = re.compile(
    r"^(?:abstract\s+|final\s+|base\s+|sealed\s+|interface\s+|mixin\s+)*class\s+(\w+)"
)
EXTENDS_RE = re.compile(r"\bextends\s+([\w.$]+(?:<[^>]*>)?)")
RIVERPOD_ANNOTATION_RE = re.compile(r"^@[Rr]iverpod\b")
CALL_METHOD_RE = re.compile(r"\bcall\s*\(")
# Non-greedy return type so the last identifier before "(" -- the function's own name -- lands
# in group 2 rather than being swallowed into the return type.
TOPLEVEL_FUNC_RE = re.compile(r"^([\w<>,.?\s]+?)\s+(\w+)\s*\(")
TOPLEVEL_PROVIDER_VAR_RE = re.compile(r"^(?:final|const)\s+(\w+)\s*=\s*\w*[Pp]rovider\w*\s*[<(]")
GO_ROUTE_RE = re.compile(r"GoRoute\(\s*path\s*:\s*['\"]([^'\"]+)['\"]")
NAMED_ROUTE_RE = re.compile(r"""['"](/[^'"]*)['"]\s*:\s*\(context\)\s*=>""")


@dataclass
class Symbol:
    name: str
    kind: str  # widget | state_management | repository | use_case | api_client | other
    file: str
    line: int
    base_class: str | None = None
    state_kind: str | None = None  # bloc | cubit | riverpod_notifier | riverpod_provider


@dataclass
class RouteEntry:
    path: str
    file: str
    line: int
    source: str  # go_router | named_route


@dataclass
class DartFileScan:
    file: str
    imports: list[str] = field(default_factory=list)
    symbols: list[Symbol] = field(default_factory=list)
    routes: list[RouteEntry] = field(default_factory=list)


def discover_dart_files(lib_dir: Path) -> list[Path]:
    files = []
    for path in sorted(lib_dir.rglob("*.dart")):
        if not path.is_file():
            continue
        try:
            if path.stat().st_size > MAX_DART_FILE_SIZE_BYTES:
                continue
        except OSError:
            continue
        files.append(path)
    return files


def _class_header(lines: list[str], start: int) -> str:
    end = start
    while "{" not in lines[end] and end + 1 < len(lines):
        end += 1
    return " ".join(line.strip() for line in lines[start : end + 1])


def _class_body(lines: list[str], start: int) -> str:
    # Brace-depth walk from the class's declaration line to its matching closing brace. Ignores
    # braces inside strings/comments -- a real analyzer's job, not a heuristic regex scanner's --
    # so a stray "{" in a string literal can throw this off; acceptable for the classification
    # heuristics (call()/Dio()/http.Client() detection) that consume the result.
    body_lines = []
    depth = 0
    started = False
    for idx in range(start, len(lines)):
        line = lines[idx]
        opens = line.count("{")
        closes = line.count("}")
        if opens:
            started = True
        depth += opens - closes
        body_lines.append(line)
        if started and depth <= 0:
            break
    return "\n".join(body_lines)


def _classify_class(
    name: str, base: str | None, body: str, riverpod_annotated: bool
) -> tuple[str, str | None]:
    if base in WIDGET_BASE_CLASSES:
        return "widget", None
    if base == "Bloc":
        return "state_management", "bloc"
    if base == "Cubit":
        return "state_management", "cubit"
    if base == "StateNotifier":
        return "state_management", "riverpod_notifier"
    if riverpod_annotated:
        # Riverpod 2.x code-gen style: `@riverpod class Foo extends _$Foo { ... }`.
        return "state_management", "riverpod_notifier"
    if name.endswith("RepositoryImpl") or name.endswith("Repository"):
        return "repository", None
    if name.endswith("UseCase"):
        return "use_case", None
    if name.endswith("ApiClient") or name.endswith("Api"):
        return "api_client", None
    if CALL_METHOD_RE.search(body):
        # A single callable `call(...)` method is the idiomatic Dart use-case shape even when
        # the class isn't named *UseCase.
        return "use_case", None
    if "Dio(" in body or "http.Client(" in body:
        return "api_client", None
    return "other", None


def _scan_routes(text: str, relative_path: str) -> list[RouteEntry]:
    routes = []
    for match in GO_ROUTE_RE.finditer(text):
        line = text.count("\n", 0, match.start()) + 1
        routes.append(
            RouteEntry(path=match.group(1), file=relative_path, line=line, source="go_router")
        )
    for match in NAMED_ROUTE_RE.finditer(text):
        line = text.count("\n", 0, match.start()) + 1
        routes.append(
            RouteEntry(path=match.group(1), file=relative_path, line=line, source="named_route")
        )
    return routes


def scan_file(text: str, relative_path: str) -> DartFileScan:
    """Heuristically classifies a .dart file's top-level imports, classes/functions/providers,
    and route declarations via regex and brace-depth tracking -- no Dart analyzer involved."""
    lines = text.splitlines()
    imports: list[str] = []
    symbols: list[Symbol] = []
    depth = 0
    pending_riverpod = False

    for i, raw_line in enumerate(lines):
        line = raw_line.strip()
        current_depth = depth
        consumed_annotation = False

        if current_depth == 0 and line:
            import_match = IMPORT_RE.match(line)
            if import_match:
                imports.append(import_match.group(1))

            class_match = CLASS_LINE_RE.match(line)
            if class_match:
                name = class_match.group(1)
                header = _class_header(lines, i)
                body = _class_body(lines, i)
                extends_match = EXTENDS_RE.search(header)
                extends = extends_match.group(1) if extends_match else None
                base = extends.split("<", 1)[0].strip() if extends else None
                kind, state_kind = _classify_class(name, base, body, pending_riverpod)
                symbols.append(
                    Symbol(
                        name=name,
                        kind=kind,
                        file=relative_path,
                        line=i + 1,
                        base_class=base,
                        state_kind=state_kind,
                    )
                )
                consumed_annotation = True
            else:
                var_match = TOPLEVEL_PROVIDER_VAR_RE.match(line)
                if var_match:
                    symbols.append(
                        Symbol(
                            name=var_match.group(1),
                            kind="state_management",
                            file=relative_path,
                            line=i + 1,
                            state_kind="riverpod_provider",
                        )
                    )
                    consumed_annotation = True
                elif pending_riverpod:
                    func_match = TOPLEVEL_FUNC_RE.match(line)
                    if func_match:
                        symbols.append(
                            Symbol(
                                name=func_match.group(2),
                                kind="state_management",
                                file=relative_path,
                                line=i + 1,
                                state_kind="riverpod_provider",
                            )
                        )
                        consumed_annotation = True

            if RIVERPOD_ANNOTATION_RE.match(line):
                pending_riverpod = True
            elif consumed_annotation:
                pending_riverpod = False
            elif not line.startswith("@"):
                pending_riverpod = False

        depth += line.count("{") - line.count("}")

    routes = _scan_routes(text, relative_path)
    return DartFileScan(file=relative_path, imports=imports, symbols=symbols, routes=routes)
