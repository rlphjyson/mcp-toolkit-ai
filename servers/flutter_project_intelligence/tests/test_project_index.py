import pytest

from flutter_project_intelligence.project_index import build_project_index
from flutter_project_intelligence.project_registry import project_id_for


def _write_project(root):
    root_ = root
    (root_ / "pubspec.yaml").write_text(
        "name: my_app\n"
        "environment:\n"
        "  sdk: '>=3.0.0 <4.0.0'\n"
        "dependencies:\n"
        "  flutter:\n"
        "    sdk: flutter\n"
        "  http: ^1.2.0\n"
    )
    lib_dir = root_ / "lib"
    (lib_dir / "repositories").mkdir(parents=True)
    (lib_dir / "widgets").mkdir(parents=True)

    (lib_dir / "main.dart").write_text(
        "import 'package:my_app/widgets/home_screen.dart';\n"
        "import 'repositories/user_repository.dart';\n"
        "\n"
        "void main() {}\n"
    )
    (lib_dir / "widgets" / "home_screen.dart").write_text(
        "import 'package:flutter/material.dart';\n"
        "import '../repositories/user_repository.dart';\n"
        "\n"
        "class HomeScreen extends StatelessWidget {\n"
        "  @override\n"
        "  Widget build(BuildContext context) => Container();\n"
        "}\n"
    )
    (lib_dir / "repositories" / "user_repository.dart").write_text(
        "class UserRepository {\n"
        "  Future<void> save() async {}\n"
        "}\n"
    )
    return root_


def test_build_project_index_raises_for_missing_pubspec(tmp_path):
    with pytest.raises(ValueError, match="pubspec.yaml"):
        build_project_index(tmp_path)


def test_build_project_index_raises_for_missing_lib_dir(tmp_path):
    (tmp_path / "pubspec.yaml").write_text("name: my_app\n")

    with pytest.raises(ValueError, match="lib/"):
        build_project_index(tmp_path)


def test_build_project_index_parses_manifest_and_files(tmp_path):
    _write_project(tmp_path)

    index = build_project_index(tmp_path)

    assert index.package_name == "my_app"
    assert index.project_id == project_id_for(tmp_path)
    assert set(index.files) == {
        "lib/main.dart",
        "lib/widgets/home_screen.dart",
        "lib/repositories/user_repository.dart",
    }


def test_build_project_index_resolves_relative_and_self_package_imports(tmp_path):
    _write_project(tmp_path)

    index = build_project_index(tmp_path)

    assert set(index.import_graph["lib/main.dart"]) == {
        "lib/widgets/home_screen.dart",
        "lib/repositories/user_repository.dart",
    }
    assert set(index.import_graph["lib/widgets/home_screen.dart"]) == {
        "lib/repositories/user_repository.dart",
    }
    # dart:*/external package: imports never resolve, so they never show up as edges.
    assert index.import_graph["lib/repositories/user_repository.dart"] == []


def test_build_project_index_builds_reverse_import_graph(tmp_path):
    _write_project(tmp_path)

    index = build_project_index(tmp_path)

    assert set(index.reverse_import_graph["lib/repositories/user_repository.dart"]) == {
        "lib/main.dart",
        "lib/widgets/home_screen.dart",
    }


def test_build_project_index_is_idempotent_for_the_same_path(tmp_path):
    _write_project(tmp_path)

    first = build_project_index(tmp_path)
    second = build_project_index(tmp_path)

    assert first.project_id == second.project_id
