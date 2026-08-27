import subprocess

import pytest

from flutter_crash_analyzer.git_blame import blame_line


def run_git(repo_path, *args):
    subprocess.run(["git", *args], cwd=repo_path, check=True, capture_output=True)


@pytest.fixture(name="repo")
def repo_fixture(tmp_path):
    run_git(tmp_path, "init", "-q")
    run_git(tmp_path, "config", "user.email", "test@example.com")
    run_git(tmp_path, "config", "user.name", "Test")

    lib_dir = tmp_path / "lib" / "widgets"
    lib_dir.mkdir(parents=True)
    (lib_dir / "my_widget.dart").write_text(
        "class MyWidget {\n  void build() {\n    final x = null;\n    x!.toString();\n  }\n}\n"
    )
    run_git(tmp_path, "add", "lib/widgets/my_widget.dart")
    run_git(tmp_path, "commit", "-q", "-m", "add MyWidget")

    return tmp_path


def test_blame_line_returns_author_and_commit_info(repo):
    result = blame_line(repo, "lib/widgets/my_widget.dart", 4)

    assert result is not None
    assert result["author"] == "Test"
    assert result["summary"] == "add MyWidget"
    assert len(result["sha"]) == 40
    assert result["date"] is not None


def test_blame_line_returns_none_for_untracked_file(repo):
    (repo / "lib" / "widgets" / "untracked.dart").write_text("class Untracked {}\n")

    result = blame_line(repo, "lib/widgets/untracked.dart", 1)

    assert result is None


def test_blame_line_returns_none_for_nonexistent_file(repo):
    result = blame_line(repo, "lib/widgets/does_not_exist.dart", 1)

    assert result is None


def test_blame_line_returns_none_for_non_git_directory(tmp_path):
    (tmp_path / "a.dart").write_text("class A {}\n")

    result = blame_line(tmp_path, "a.dart", 1)

    assert result is None
