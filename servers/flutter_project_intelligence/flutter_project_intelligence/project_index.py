from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from flutter_project_intelligence.dart_scanner import DartFileScan, discover_dart_files, scan_file
from flutter_project_intelligence.project_registry import project_id_for
from flutter_project_intelligence.pubspec_parser import parse_pubspec


@dataclass
class ProjectIndex:
    project_id: str
    root: Path
    package_name: str
    flutter_sdk_constraint: str | None
    dependencies: dict[str, str]
    dev_dependencies: dict[str, str]
    files: dict[str, DartFileScan] = field(default_factory=dict)
    import_graph: dict[str, list[str]] = field(default_factory=dict)
    reverse_import_graph: dict[str, list[str]] = field(default_factory=dict)


def _resolve_relative_import(target: str, importing_file: str) -> str:
    importing_dir = PurePosixPath(importing_file).parent
    parts: list[str] = []
    for part in (importing_dir / target).parts:
        if part == "..":
            if parts:
                parts.pop()
        elif part in (".", ""):
            continue
        else:
            parts.append(part)
    return "/".join(parts)


def _resolve_import(target: str, importing_file: str, package_name: str) -> str | None:
    if target.startswith("dart:"):
        return None
    if target.startswith("package:"):
        prefix = f"package:{package_name}/"
        if not target.startswith(prefix):
            return None  # a dependency's own package, not this project's
        return f"lib/{target[len(prefix):]}"
    return _resolve_relative_import(target, importing_file)


def build_project_index(project_root: Path) -> ProjectIndex:
    """Scans a Flutter project's pubspec.yaml and lib/ directory into a full in-memory index:
    every .dart file's classified symbols and routes, plus the project's own internal import
    graph."""
    pubspec_path = project_root / "pubspec.yaml"
    if not pubspec_path.is_file():
        raise ValueError(f"No pubspec.yaml found in '{project_root}'. Not a Flutter/Dart project.")

    lib_dir = project_root / "lib"
    if not lib_dir.is_dir():
        raise ValueError(f"No lib/ directory found in '{project_root}'. Not a Flutter/Dart project.")

    manifest = parse_pubspec(pubspec_path)

    files: dict[str, DartFileScan] = {}
    for path in discover_dart_files(lib_dir):
        relative = path.relative_to(project_root).as_posix()
        text = path.read_text(encoding="utf-8", errors="ignore")
        files[relative] = scan_file(text, relative)

    # Internal-only: an import graph edge is recorded only when it resolves to a file this
    # project actually indexed, so external packages and dart: imports never appear in it.
    import_graph: dict[str, list[str]] = {relative: [] for relative in files}
    reverse_import_graph: dict[str, list[str]] = {relative: [] for relative in files}
    for relative, scan in files.items():
        for target in scan.imports:
            resolved = _resolve_import(target, relative, manifest.package_name)
            if resolved is not None and resolved in files:
                import_graph[relative].append(resolved)
                reverse_import_graph[resolved].append(relative)

    return ProjectIndex(
        project_id=project_id_for(project_root),
        root=project_root.resolve(),
        package_name=manifest.package_name,
        flutter_sdk_constraint=manifest.flutter_sdk_constraint,
        dependencies=manifest.dependencies,
        dev_dependencies=manifest.dev_dependencies,
        files=files,
        import_graph=import_graph,
        reverse_import_graph=reverse_import_graph,
    )
