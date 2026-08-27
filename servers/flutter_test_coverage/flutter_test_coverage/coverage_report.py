from pathlib import Path

from flutter_test_coverage.lcov_parser import FileCoverage


def coverage_percent(fc: FileCoverage) -> float:
    if fc.lines_found == 0:
        return 0.0
    return round(fc.lines_hit / fc.lines_found * 100, 1)


def _relative_directory(file: str) -> str:
    # lcov SF: paths from `flutter test --coverage` are typically project-root-relative
    # (e.g. "lib/widgets/foo.dart") -- group by the path under lib/ so unrelated top-level
    # dirs (test/, bin/) don't get lumped into the same bucket as library code.
    parts = Path(file).parts
    if "lib" in parts:
        idx = parts.index("lib")
        rel_parts = parts[idx + 1 : -1]
    else:
        rel_parts = parts[:-1]
    return "/".join(rel_parts) if rel_parts else "."


def summarize(files: dict[str, FileCoverage]) -> dict:
    total_found = sum(fc.lines_found for fc in files.values())
    total_hit = sum(fc.lines_hit for fc in files.values())
    overall = round(total_hit / total_found * 100, 1) if total_found else 0.0

    per_directory_totals: dict[str, list[int]] = {}
    for fc in files.values():
        directory = _relative_directory(fc.file)
        totals = per_directory_totals.setdefault(directory, [0, 0])
        totals[0] += fc.lines_found
        totals[1] += fc.lines_hit

    per_directory = {
        directory: round(hit / found * 100, 1) if found else 0.0
        for directory, (found, hit) in per_directory_totals.items()
    }

    return {
        "total_files": len(files),
        "overall_line_coverage_percent": overall,
        "per_directory": per_directory,
    }


def list_low_coverage(files: dict[str, FileCoverage], threshold: float) -> list[dict]:
    scored = sorted(((coverage_percent(fc), fc) for fc in files.values()), key=lambda pair: pair[0])
    return [
        {
            "file": fc.file,
            "coverage_percent": percent,
            "lines_found": fc.lines_found,
            "lines_hit": fc.lines_hit,
        }
        for percent, fc in scored
        if percent < threshold
    ]


def get_uncovered_lines(fc: FileCoverage) -> list[int]:
    return sorted(line for line, hits in fc.line_hits.items() if hits == 0)
