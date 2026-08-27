import pytest

from flutter_code_migration.scanner import create_migration_plan, scan_for_legacy_patterns


@pytest.fixture(name="project")
def project_fixture(tmp_path):
    lib = tmp_path / "lib"
    (lib / "widgets").mkdir(parents=True)

    (lib / "widgets" / "buttons.dart").write_text(
        "import 'package:flutter/material.dart';\n"
        "\n"
        "class MyButtons extends StatelessWidget {\n"
        "  Widget build(BuildContext context) {\n"
        "    return RaisedButton(onPressed: () {}, child: Text('go'));\n"
        "  }\n"
        "}\n"
    )
    (lib / "widgets" / "nav.dart").write_text(
        "void openDetails(BuildContext context) {\n"
        "  Navigator.pushNamed(context, '/details');\n"
        "  Navigator.pop(context);\n"
        "}\n"
    )
    (lib / "main.dart").write_text("void main() {}\n")

    return tmp_path


def test_scan_finds_mechanical_matches_for_deprecated_widgets(project):
    matches = scan_for_legacy_patterns(project, "deprecated_widgets")

    assert len(matches) == 1
    match = matches[0]
    assert match["migration_id"] == "deprecated_widgets"
    assert match["category"] == "mechanical"
    assert match["matched_text"] == "RaisedButton"
    assert match["line"] == 5
    assert match["file"].endswith("buttons.dart")


def test_scan_finds_manual_required_matches_for_navigator_to_gorouter(project):
    matches = scan_for_legacy_patterns(project, "navigator_to_gorouter")

    matched_texts = {m["matched_text"] for m in matches}
    assert matched_texts == {"Navigator.pushNamed(", "Navigator.pop("}
    assert all(m["category"] == "manual_required" for m in matches)
    assert all(m["file"].endswith("nav.dart") for m in matches)


def test_scan_returns_no_matches_for_migration_with_no_hits(project):
    assert scan_for_legacy_patterns(project, "bloc_to_riverpod") == []


def test_scan_rejects_unknown_migration(project):
    with pytest.raises(ValueError, match="Unknown migration"):
        scan_for_legacy_patterns(project, "not_a_real_migration")


def test_scan_handles_missing_lib_directory_gracefully(tmp_path):
    assert scan_for_legacy_patterns(tmp_path, "deprecated_widgets") == []


def test_create_migration_plan_groups_matches_by_file(project):
    plan = create_migration_plan(project, "navigator_to_gorouter")

    assert plan["migration"] == "navigator_to_gorouter"
    assert plan["total_matches"] == 2
    assert plan["mechanical_count"] == 0
    assert plan["manual_required_count"] == 2
    assert len(plan["affected_files"]) == 1
    affected = plan["affected_files"][0]
    assert affected["match_count"] == 2
    assert affected["file"].endswith("nav.dart")


def test_create_migration_plan_reports_mechanical_and_manual_counts_for_deprecated_widgets(project):
    plan = create_migration_plan(project, "deprecated_widgets")

    assert plan["total_matches"] == 1
    assert plan["mechanical_count"] == 1
    assert plan["manual_required_count"] == 0
