import subprocess

import pytest

from dev_environment.git_log import get_recent_commits


def run_git(repo_path, *args):
    subprocess.run(["git", *args], cwd=repo_path, check=True, capture_output=True)


@pytest.fixture(name="repo")
def repo_fixture(tmp_path):
    run_git(tmp_path, "init", "-q")
    run_git(tmp_path, "config", "user.email", "test@example.com")
    run_git(tmp_path, "config", "user.name", "Test")

    (tmp_path / "a.txt").write_text("a\n")
    run_git(tmp_path, "add", "a.txt")
    run_git(tmp_path, "commit", "-q", "-m", "first commit")

    (tmp_path / "b.txt").write_text("b\n")
    run_git(tmp_path, "add", "b.txt")
    run_git(tmp_path, "commit", "-q", "-m", "second commit")

    return tmp_path


def test_get_recent_commits_returns_commits_newest_first(repo):
    commits = get_recent_commits(repo)

    assert len(commits) == 2
    assert commits[0].message == "second commit"
    assert commits[1].message == "first commit"
    assert commits[0].author == "Test"
    assert len(commits[0].sha) == 40


def test_get_recent_commits_respects_limit(repo):
    commits = get_recent_commits(repo, limit=1)
    assert len(commits) == 1
    assert commits[0].message == "second commit"


def test_get_recent_commits_raises_for_non_git_directory(tmp_path):
    with pytest.raises(subprocess.CalledProcessError):
        get_recent_commits(tmp_path)
