from flutter_project_intelligence.pubspec_parser import parse_pubspec


def test_parse_pubspec_extracts_name_sdk_and_dependencies(tmp_path):
    pubspec = tmp_path / "pubspec.yaml"
    pubspec.write_text(
        "name: my_app\n"
        "description: A sample app.\n"
        "environment:\n"
        "  sdk: '>=3.0.0 <4.0.0'\n"
        "  flutter: '>=3.10.0'\n"
        "dependencies:\n"
        "  flutter:\n"
        "    sdk: flutter\n"
        "  http: ^1.2.0\n"
        "  dio: ^5.4.0\n"
        "dev_dependencies:\n"
        "  flutter_test:\n"
        "    sdk: flutter\n"
        "  build_runner: ^2.4.0\n"
    )

    manifest = parse_pubspec(pubspec)

    assert manifest.package_name == "my_app"
    assert manifest.flutter_sdk_constraint == ">=3.10.0"
    assert manifest.dependencies == {"flutter": "any", "http": "^1.2.0", "dio": "^5.4.0"}
    assert manifest.dev_dependencies == {"flutter_test": "any", "build_runner": "^2.4.0"}


def test_parse_pubspec_falls_back_to_dart_sdk_constraint_when_no_flutter_range(tmp_path):
    pubspec = tmp_path / "pubspec.yaml"
    pubspec.write_text("name: cli_tool\nenvironment:\n  sdk: '>=3.0.0 <4.0.0'\n")

    manifest = parse_pubspec(pubspec)

    assert manifest.flutter_sdk_constraint == ">=3.0.0 <4.0.0"


def test_parse_pubspec_handles_missing_sections(tmp_path):
    pubspec = tmp_path / "pubspec.yaml"
    pubspec.write_text("name: bare_package\n")

    manifest = parse_pubspec(pubspec)

    assert manifest.package_name == "bare_package"
    assert manifest.flutter_sdk_constraint is None
    assert manifest.dependencies == {}
    assert manifest.dev_dependencies == {}


def test_parse_pubspec_handles_git_dependency_with_no_version(tmp_path):
    pubspec = tmp_path / "pubspec.yaml"
    pubspec.write_text(
        "name: my_app\n"
        "dependencies:\n"
        "  my_lib:\n"
        "    git:\n"
        "      url: https://example.com/my_lib.git\n"
    )

    manifest = parse_pubspec(pubspec)

    assert manifest.dependencies == {"my_lib": "any"}
