from flutter_test_coverage.missing_tests import find_missing_test_files


def _write(path, content=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_find_missing_test_files_accepts_mirrored_path_match(tmp_path):
    _write(tmp_path / "lib" / "widgets" / "foo.dart")
    _write(tmp_path / "test" / "widgets" / "foo_test.dart")

    assert find_missing_test_files(tmp_path) == []


def test_find_missing_test_files_accepts_flat_match_anywhere_under_test(tmp_path):
    _write(tmp_path / "lib" / "services" / "bar.dart")
    _write(tmp_path / "test" / "unit" / "bar_test.dart")

    assert find_missing_test_files(tmp_path) == []


def test_find_missing_test_files_reports_genuinely_missing_source_file(tmp_path):
    _write(tmp_path / "lib" / "services" / "baz.dart")

    result = find_missing_test_files(tmp_path)

    assert result == [
        {
            "source_file": "lib/services/baz.dart",
            "expected_test_file": "services/baz_test.dart",
        }
    ]


def test_find_missing_test_files_skips_generated_files(tmp_path):
    _write(tmp_path / "lib" / "models" / "user.g.dart")
    _write(tmp_path / "lib" / "models" / "user.freezed.dart")

    assert find_missing_test_files(tmp_path) == []


def test_find_missing_test_files_mixed_tree(tmp_path):
    _write(tmp_path / "lib" / "a.dart")
    _write(tmp_path / "test" / "a_test.dart")
    _write(tmp_path / "lib" / "b.dart")

    result = find_missing_test_files(tmp_path)

    assert result == [{"source_file": "lib/b.dart", "expected_test_file": "b_test.dart"}]


def test_find_missing_test_files_returns_empty_when_no_lib_dir(tmp_path):
    assert find_missing_test_files(tmp_path) == []
