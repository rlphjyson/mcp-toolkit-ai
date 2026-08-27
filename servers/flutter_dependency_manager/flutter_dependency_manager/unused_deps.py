import re
from pathlib import Path

from flutter_dependency_manager.pubspec_parser import parse_pubspec

_IMPORT_RE = re.compile(r"""import\s+['"]package:([a-zA-Z0-9_]+)/""")

_NEVER_DIRECTLY_IMPORTED = {"flutter", "flutter_test", "cupertino_icons"}


def find_unused_dependencies(project_path: Path) -> list[str]:
    pubspec = parse_pubspec(project_path / "pubspec.yaml")
    declared = set(pubspec["dependencies"]) - _NEVER_DIRECTLY_IMPORTED

    imported: set[str] = set()
    lib_dir = project_path / "lib"
    if lib_dir.is_dir():
        for dart_file in lib_dir.rglob("*.dart"):
            text = dart_file.read_text(errors="ignore")
            imported.update(_IMPORT_RE.findall(text))

    return sorted(declared - imported)
