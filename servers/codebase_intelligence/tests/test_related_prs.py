from codebase_intelligence.git_history import CommitInfo
from codebase_intelligence.github_prs import PullRequestRef
from codebase_intelligence.related_prs import find_related_prs


class FakeGitHubClient:
    def __init__(self, prs_by_sha: dict[str, list[PullRequestRef]]) -> None:
        self._prs_by_sha = prs_by_sha
        self.queried_shas: list[str] = []

    def get_prs_for_commit(self, github_repo: str, sha: str) -> list[PullRequestRef]:
        self.queried_shas.append(sha)
        return self._prs_by_sha.get(sha, [])


def test_find_related_prs_dedupes_by_pr_number():
    pr = PullRequestRef(number=42, title="Fix bug", url="https://github.com/o/r/pull/42")
    commits = [
        CommitInfo(sha="a", author="x", date="d", message="m1"),
        CommitInfo(sha="b", author="x", date="d", message="m2"),
    ]
    github = FakeGitHubClient({"a": [pr], "b": [pr]})

    related = find_related_prs(commits, "o/r", github)

    assert related == [pr]


def test_find_related_prs_stops_at_limit():
    commits = [CommitInfo(sha=str(i), author="x", date="d", message="m") for i in range(10)]
    github = FakeGitHubClient(
        {str(i): [PullRequestRef(number=i, title=f"PR {i}", url="u")] for i in range(10)}
    )

    related = find_related_prs(commits, "o/r", github, limit=3)

    assert len(related) == 3


def test_find_related_prs_returns_empty_when_no_commits_have_prs():
    commits = [CommitInfo(sha="a", author="x", date="d", message="m")]
    github = FakeGitHubClient({})

    assert find_related_prs(commits, "o/r", github) == []
