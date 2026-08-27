from pathlib import Path

from flutter_code_migration.migration_rules import MIGRATIONS, MigrationRule, require_known_migration


def _mechanical_rules(migration: str) -> list[MigrationRule]:
    return [rule for rule in MIGRATIONS[migration] if rule.replacement is not None]


def preview_transformation(file_path: Path, migration: str) -> dict:
    require_known_migration(migration)
    if not file_path.is_file():
        raise FileNotFoundError(f"No such file: {file_path}")

    original_content = file_path.read_text(encoding="utf-8")
    transformed_content = original_content
    changes_applied = 0
    for rule in _mechanical_rules(migration):
        replacement = rule.replacement
        assert replacement is not None  # guaranteed by _mechanical_rules' filter
        transformed_content, count = rule.pattern.subn(replacement, transformed_content)
        changes_applied += count

    return {
        "file": str(file_path),
        "original_content": original_content,
        "transformed_content": transformed_content,
        "changes_applied": changes_applied,
    }


def apply_transformation(file_path: Path, migration: str, dry_run: bool = True) -> dict:
    require_known_migration(migration)
    if not _mechanical_rules(migration):
        raise ValueError(
            f"Migration '{migration}' has no mechanical rules -- every rule in it is "
            "manual_required, so nothing can be safely auto-applied. Use scan_for_legacy_patterns "
            "or create_migration_plan to get guidance for manual migration instead."
        )

    preview = preview_transformation(file_path, migration)
    if dry_run:
        return preview

    file_path.write_text(preview["transformed_content"], encoding="utf-8")
    return {
        "file": preview["file"],
        "changes_applied": preview["changes_applied"],
        "written": True,
    }
