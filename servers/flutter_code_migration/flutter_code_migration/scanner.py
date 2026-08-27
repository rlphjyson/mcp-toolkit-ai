from pathlib import Path

from flutter_code_migration.config import LIB_GLOB_PATTERN
from flutter_code_migration.migration_rules import MIGRATIONS, require_known_migration


def scan_for_legacy_patterns(project_path: Path, migration: str) -> list[dict]:
    require_known_migration(migration)
    rules = MIGRATIONS[migration]

    matches = []
    for dart_file in sorted(project_path.glob(LIB_GLOB_PATTERN)):
        if not dart_file.is_file():
            continue
        text = dart_file.read_text(encoding="utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for rule in rules:
                for match in rule.pattern.finditer(line):
                    matches.append(
                        {
                            "migration_id": migration,
                            "category": rule.category,
                            "description": rule.description,
                            "file": str(dart_file),
                            "line": line_number,
                            "matched_text": match.group(0),
                        }
                    )
    return matches


def create_migration_plan(project_path: Path, migration: str) -> dict:
    matches = scan_for_legacy_patterns(project_path, migration)

    by_file: dict[str, list[dict]] = {}
    for match in matches:
        by_file.setdefault(match["file"], []).append(match)

    return {
        "migration": migration,
        "total_matches": len(matches),
        "mechanical_count": sum(1 for m in matches if m["category"] == "mechanical"),
        "manual_required_count": sum(1 for m in matches if m["category"] == "manual_required"),
        "affected_files": [
            {"file": file, "match_count": len(file_matches), "matches": file_matches}
            for file, file_matches in by_file.items()
        ],
    }
