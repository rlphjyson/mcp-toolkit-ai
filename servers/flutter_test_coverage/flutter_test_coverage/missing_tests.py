from pathlib import Path

GENERATED_SUFFIXES = (".g.dart", ".freezed.dart")


def find_missing_test_files(project_path: Path) -> list[dict]:
    lib_dir = project_path / "lib"
    test_dir = project_path / "test"
    if not lib_dir.is_dir():
        return []

    # Flutter projects vary in whether test/ mirrors lib/'s directory structure exactly, so a
    # source file counts as tested if either the mirrored path exists, or a same-named
    # "<name>_test.dart" exists anywhere under test/.
    existing_test_names = (
        {p.name for p in test_dir.rglob("*_test.dart")} if test_dir.is_dir() else set()
    )

    missing = []
    for source_file in sorted(lib_dir.rglob("*.dart")):
        if any(source_file.name.endswith(suffix) for suffix in GENERATED_SUFFIXES):
            continue

        relative = source_file.relative_to(lib_dir)
        expected_relative = relative.parent / f"{source_file.stem}_test.dart"
        expected_test_file = test_dir / expected_relative
        expected_test_name = f"{source_file.stem}_test.dart"

        if expected_test_file.is_file() or expected_test_name in existing_test_names:
            continue

        missing.append(
            {
                "source_file": str(source_file.relative_to(project_path)),
                "expected_test_file": str(expected_relative),
            }
        )

    return missing
