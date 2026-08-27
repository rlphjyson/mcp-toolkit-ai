import re
from pathlib import Path

import yaml

# Matches both single- and double-quoted Dart import directives, one per line -- Dart import
# statements are always single-line, so a line-anchored regex is enough without a real parser.
IMPORT_RE = re.compile(r"""^\s*import\s+['"]([^'"]+)['"]""", re.MULTILINE)


def get_project_name(project_path: Path) -> str:
    pubspec_path = project_path / "pubspec.yaml"
    if not pubspec_path.is_file():
        raise ValueError(f"No pubspec.yaml found in '{project_path}'.")
    data = yaml.safe_load(pubspec_path.read_text(encoding="utf-8"))
    name = data.get("name") if isinstance(data, dict) else None
    if not name:
        raise ValueError(f"pubspec.yaml in '{project_path}' has no 'name' field.")
    return str(name)


def _resolve_import(raw_import: str, file_dir: Path, lib_dir: Path, project_name: str) -> Path | None:
    if raw_import.startswith("dart:"):
        return None
    if raw_import.startswith("package:"):
        prefix = f"package:{project_name}/"
        if not raw_import.startswith(prefix):
            return None  # a different package -- external dependency or another project
        return (lib_dir / raw_import[len(prefix) :]).resolve()
    return (file_dir / raw_import).resolve()


def build_import_graph(project_path: Path) -> dict[str, list[str]]:
    """Scans a Flutter project's lib/ tree and returns a map of each .dart file (as a path
    relative to lib/) to the project-relative paths of the files it imports. Imports of external
    packages, other projects, or dart: SDK libraries are dropped -- only self-imports matter for
    architecture checks."""
    project_path = project_path.resolve()
    project_name = get_project_name(project_path)
    lib_dir = project_path / "lib"
    if not lib_dir.is_dir():
        raise ValueError(f"No lib/ directory found in '{project_path}'.")

    dart_files = sorted(lib_dir.rglob("*.dart"))
    known_files = {f.resolve() for f in dart_files}

    graph: dict[str, list[str]] = {}
    for file_path in dart_files:
        rel = file_path.relative_to(lib_dir).as_posix()
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        imports = []
        for raw_import in IMPORT_RE.findall(text):
            resolved = _resolve_import(raw_import, file_path.parent, lib_dir, project_name)
            if resolved is None or resolved not in known_files:
                continue
            imports.append(resolved.relative_to(lib_dir).as_posix())
        graph[rel] = imports
    return graph
