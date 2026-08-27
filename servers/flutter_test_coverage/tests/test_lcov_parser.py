import pytest

from flutter_test_coverage.lcov_parser import parse_lcov

# lib/foo.dart appears twice (as a real lcov report can when a source file is exercised by
# more than one test target) -- line 2's hit count (0 the first time, 3 the second) must be
# summed, not overwritten, when the records are merged.
FIXTURE = """\
SF:lib/foo.dart
DA:1,1
DA:2,0
LF:2
LH:1
end_of_record
SF:lib/bar.dart
DA:1,0
DA:2,0
DA:3,5
LF:3
LH:1
end_of_record
SF:lib/foo.dart
DA:1,2
DA:2,3
LF:2
LH:2
end_of_record
"""


def test_parse_lcov_returns_one_entry_per_distinct_file():
    files = parse_lcov(FIXTURE)
    assert set(files) == {"lib/foo.dart", "lib/bar.dart"}


def test_parse_lcov_merges_duplicate_sf_records_by_summing_line_hits():
    files = parse_lcov(FIXTURE)
    foo = files["lib/foo.dart"]
    assert foo.line_hits == {1: 3, 2: 3}
    assert foo.lines_found == 2
    assert foo.lines_hit == 2


def test_parse_lcov_parses_a_single_record_file():
    files = parse_lcov(FIXTURE)
    bar = files["lib/bar.dart"]
    assert bar.line_hits == {1: 0, 2: 0, 3: 5}
    assert bar.lines_found == 3
    assert bar.lines_hit == 1


def test_parse_lcov_rejects_text_with_no_sf_records():
    with pytest.raises(ValueError, match="No SF: records found"):
        parse_lcov("this is not an lcov report\n")


def test_parse_lcov_rejects_empty_text():
    with pytest.raises(ValueError, match="No SF: records found"):
        parse_lcov("")
