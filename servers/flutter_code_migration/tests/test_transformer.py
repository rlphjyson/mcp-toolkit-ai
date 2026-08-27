import pytest

from flutter_code_migration.transformer import apply_transformation, preview_transformation


@pytest.fixture(name="dart_file")
def dart_file_fixture(tmp_path):
    file_path = tmp_path / "buttons.dart"
    file_path.write_text(
        "class MyButtons extends StatelessWidget {\n"
        "  Widget build(BuildContext context) {\n"
        "    return RaisedButton(onPressed: () {}, child: Text('go'));\n"
        "  }\n"
        "}\n"
    )
    return file_path


def test_preview_transformation_returns_transformed_content_without_writing(dart_file):
    original = dart_file.read_text()

    result = preview_transformation(dart_file, "deprecated_widgets")

    assert result["original_content"] == original
    assert "ElevatedButton" in result["transformed_content"]
    assert "RaisedButton" not in result["transformed_content"]
    assert result["changes_applied"] == 1
    assert dart_file.read_text() == original


def test_preview_transformation_reports_zero_changes_when_nothing_matches(tmp_path):
    file_path = tmp_path / "clean.dart"
    file_path.write_text("class Clean extends StatelessWidget {}\n")

    result = preview_transformation(file_path, "deprecated_widgets")

    assert result["transformed_content"] == result["original_content"]
    assert result["changes_applied"] == 0


def test_preview_transformation_raises_for_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        preview_transformation(tmp_path / "missing.dart", "deprecated_widgets")


def test_apply_transformation_dry_run_true_matches_preview_and_does_not_write(dart_file):
    original = dart_file.read_text()

    result = apply_transformation(dart_file, "deprecated_widgets", dry_run=True)

    assert result["changes_applied"] == 1
    assert "ElevatedButton" in result["transformed_content"]
    assert dart_file.read_text() == original


def test_apply_transformation_dry_run_false_writes_the_file(dart_file):
    result = apply_transformation(dart_file, "deprecated_widgets", dry_run=False)

    assert result == {
        "file": str(dart_file),
        "changes_applied": 1,
        "written": True,
    }
    on_disk = dart_file.read_text()
    assert "ElevatedButton" in on_disk
    assert "RaisedButton" not in on_disk


def test_apply_transformation_refuses_all_manual_required_migration(dart_file):
    with pytest.raises(ValueError, match="no mechanical rules"):
        apply_transformation(dart_file, "navigator_to_gorouter", dry_run=False)


def test_apply_transformation_rejects_unknown_migration(dart_file):
    with pytest.raises(ValueError, match="Unknown migration"):
        apply_transformation(dart_file, "not_a_real_migration", dry_run=False)


def test_apply_transformation_raises_for_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        apply_transformation(tmp_path / "missing.dart", "deprecated_widgets", dry_run=False)
