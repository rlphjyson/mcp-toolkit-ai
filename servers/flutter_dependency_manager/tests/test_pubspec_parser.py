import pytest

from flutter_dependency_manager.pubspec_parser import parse_pubspec

VALID_PUBSPEC = """
name: sample_app
description: A sample app.
dependencies:
  flutter:
    sdk: flutter
  http: ^1.2.0
  local_pkg:
    path: ../local_pkg
  git_pkg:
    git:
      url: https://github.com/example/git_pkg.git
  no_constraint: any
  null_constraint:
dev_dependencies:
  flutter_test:
    sdk: flutter
  build_runner: ^2.4.0
"""

NO_NAME_PUBSPEC = """
description: Missing a name key.
dependencies:
  http: ^1.2.0
"""


def test_parse_pubspec_normalizes_all_constraint_shapes(tmp_path):
    pubspec_path = tmp_path / "pubspec.yaml"
    pubspec_path.write_text(VALID_PUBSPEC)

    result = parse_pubspec(pubspec_path)

    assert result["name"] == "sample_app"
    assert result["dependencies"]["flutter"] == "sdk:flutter"
    assert result["dependencies"]["http"] == "^1.2.0"
    assert result["dependencies"]["local_pkg"] == "path:../local_pkg"
    assert result["dependencies"]["git_pkg"] == "git:https://github.com/example/git_pkg.git"
    assert result["dependencies"]["no_constraint"] == "any"
    assert result["dependencies"]["null_constraint"] == "any"


def test_parse_pubspec_reads_dev_dependencies(tmp_path):
    pubspec_path = tmp_path / "pubspec.yaml"
    pubspec_path.write_text(VALID_PUBSPEC)

    result = parse_pubspec(pubspec_path)

    assert result["dev_dependencies"]["flutter_test"] == "sdk:flutter"
    assert result["dev_dependencies"]["build_runner"] == "^2.4.0"


def test_parse_pubspec_missing_file_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        parse_pubspec(tmp_path / "pubspec.yaml")


def test_parse_pubspec_missing_name_raises_value_error(tmp_path):
    pubspec_path = tmp_path / "pubspec.yaml"
    pubspec_path.write_text(NO_NAME_PUBSPEC)

    with pytest.raises(ValueError, match="no top-level 'name' key"):
        parse_pubspec(pubspec_path)


def test_parse_pubspec_with_no_dependencies_section(tmp_path):
    pubspec_path = tmp_path / "pubspec.yaml"
    pubspec_path.write_text("name: bare_app\n")

    result = parse_pubspec(pubspec_path)

    assert result["dependencies"] == {}
    assert result["dev_dependencies"] == {}
