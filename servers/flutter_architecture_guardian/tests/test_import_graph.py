import pytest

from flutter_architecture_guardian.import_graph import build_import_graph, get_project_name


@pytest.fixture(name="project")
def project_fixture(tmp_path):
    (tmp_path / "pubspec.yaml").write_text("name: sample_app\ndescription: test\n")
    lib = tmp_path / "lib"
    (lib / "presentation").mkdir(parents=True)
    (lib / "domain" / "entities").mkdir(parents=True)
    (lib / "data").mkdir(parents=True)

    (lib / "domain" / "entities" / "user.dart").write_text("class User {}\n")
    (lib / "presentation" / "home_screen.dart").write_text(
        "import 'dart:async';\n"
        "import 'package:flutter/material.dart';\n"
        "import 'package:sample_app/domain/entities/user.dart';\n"
        "import '../data/user_repository_impl.dart';\n"
        "class HomeScreen {}\n"
    )
    (lib / "data" / "user_repository_impl.dart").write_text(
        "import '../domain/entities/user.dart';\nclass UserRepositoryImpl {}\n"
    )
    return tmp_path


def test_get_project_name_reads_pubspec(project):
    assert get_project_name(project) == "sample_app"


def test_get_project_name_requires_pubspec(tmp_path):
    with pytest.raises(ValueError, match="No pubspec.yaml"):
        get_project_name(tmp_path)


def test_get_project_name_requires_name_field(tmp_path):
    (tmp_path / "pubspec.yaml").write_text("description: no name here\n")
    with pytest.raises(ValueError, match="no 'name' field"):
        get_project_name(tmp_path)


def test_build_import_graph_requires_lib_dir(tmp_path):
    (tmp_path / "pubspec.yaml").write_text("name: sample_app\n")
    with pytest.raises(ValueError, match="No lib/ directory"):
        build_import_graph(tmp_path)


def test_graph_contains_every_dart_file(project):
    graph = build_import_graph(project)
    assert set(graph) == {
        "domain/entities/user.dart",
        "presentation/home_screen.dart",
        "data/user_repository_impl.dart",
    }


def test_dart_and_external_package_imports_are_dropped(project):
    graph = build_import_graph(project)
    assert graph["presentation/home_screen.dart"] == [
        "domain/entities/user.dart",
        "data/user_repository_impl.dart",
    ]


def test_relative_import_is_resolved_against_file_directory(project):
    graph = build_import_graph(project)
    assert graph["data/user_repository_impl.dart"] == ["domain/entities/user.dart"]


def test_package_self_import_is_resolved_against_lib_dir(project):
    graph = build_import_graph(project)
    assert "domain/entities/user.dart" in graph["presentation/home_screen.dart"]


def test_import_of_a_nonexistent_file_is_dropped(tmp_path):
    (tmp_path / "pubspec.yaml").write_text("name: sample_app\n")
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "a.dart").write_text("import 'missing.dart';\n")

    graph = build_import_graph(tmp_path)

    assert graph["a.dart"] == []
