from flutter_dependency_manager.unused_deps import find_unused_dependencies

PUBSPEC = """
name: sample_app
dependencies:
  flutter:
    sdk: flutter
  cupertino_icons: ^1.0.0
  used_pkg: ^1.0.0
  unused_pkg: ^1.0.0
  another_unused_pkg: ^2.0.0
dev_dependencies:
  flutter_test:
    sdk: flutter
"""


def _make_project(tmp_path):
    (tmp_path / "pubspec.yaml").write_text(PUBSPEC)
    lib_dir = tmp_path / "lib"
    (lib_dir / "src").mkdir(parents=True)
    (lib_dir / "main.dart").write_text(
        "import 'package:flutter/material.dart';\nimport 'package:used_pkg/used_pkg.dart';\n"
    )
    (lib_dir / "src" / "widget.dart").write_text(
        "import 'package:used_pkg/widgets.dart';\n\nvoid build() {}\n"
    )
    return tmp_path


def test_find_unused_dependencies_flags_never_imported_packages(tmp_path):
    project = _make_project(tmp_path)

    unused = find_unused_dependencies(project)

    assert unused == ["another_unused_pkg", "unused_pkg"]


def test_find_unused_dependencies_ignores_conventional_sdk_packages(tmp_path):
    project = _make_project(tmp_path)

    unused = find_unused_dependencies(project)

    assert "flutter" not in unused
    assert "cupertino_icons" not in unused


def test_find_unused_dependencies_with_no_lib_directory(tmp_path):
    (tmp_path / "pubspec.yaml").write_text(PUBSPEC)

    unused = find_unused_dependencies(tmp_path)

    assert unused == ["another_unused_pkg", "unused_pkg", "used_pkg"]
