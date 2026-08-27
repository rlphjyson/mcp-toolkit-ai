from flutter_test_coverage.coverage_report import (
    coverage_percent,
    get_uncovered_lines,
    list_low_coverage,
    summarize,
)
from flutter_test_coverage.lcov_parser import FileCoverage

WELL_COVERED = FileCoverage(
    file="lib/widgets/foo.dart",
    lines_found=10,
    lines_hit=9,
    line_hits={i: 1 for i in range(1, 10)} | {10: 0},
)
POORLY_COVERED = FileCoverage(
    file="lib/services/bar.dart",
    lines_found=10,
    lines_hit=2,
    line_hits={1: 1, 2: 1} | {i: 0 for i in range(3, 11)},
)
EMPTY = FileCoverage(file="lib/empty.dart", lines_found=0, lines_hit=0, line_hits={})

FILES = {fc.file: fc for fc in (WELL_COVERED, POORLY_COVERED, EMPTY)}


def test_coverage_percent_computes_rounded_percentage():
    assert coverage_percent(WELL_COVERED) == 90.0
    assert coverage_percent(POORLY_COVERED) == 20.0


def test_coverage_percent_is_zero_for_files_with_no_lines():
    assert coverage_percent(EMPTY) == 0.0


def test_summarize_reports_totals_and_overall_percentage():
    summary = summarize(FILES)
    assert summary["total_files"] == 3
    assert summary["overall_line_coverage_percent"] == 55.0


def test_summarize_groups_per_directory_relative_to_lib():
    summary = summarize(FILES)
    assert summary["per_directory"] == {
        "widgets": 90.0,
        "services": 20.0,
        ".": 0.0,
    }


def test_list_low_coverage_filters_and_sorts_ascending():
    low = list_low_coverage(FILES, threshold=50.0)
    assert [entry["file"] for entry in low] == ["lib/empty.dart", "lib/services/bar.dart"]
    assert low[1] == {
        "file": "lib/services/bar.dart",
        "coverage_percent": 20.0,
        "lines_found": 10,
        "lines_hit": 2,
    }


def test_list_low_coverage_excludes_files_at_or_above_threshold():
    low = list_low_coverage(FILES, threshold=10.0)
    assert [entry["file"] for entry in low] == ["lib/empty.dart"]


def test_get_uncovered_lines_returns_sorted_zero_hit_lines():
    assert get_uncovered_lines(WELL_COVERED) == [10]
    assert get_uncovered_lines(POORLY_COVERED) == [3, 4, 5, 6, 7, 8, 9, 10]


def test_get_uncovered_lines_empty_when_fully_covered():
    fully_covered = FileCoverage(file="lib/ok.dart", lines_found=2, lines_hit=2, line_hits={1: 1, 2: 1})
    assert get_uncovered_lines(fully_covered) == []
