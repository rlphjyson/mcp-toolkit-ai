from dataclasses import dataclass, field
from typing import Protocol

import httpx

from issue_tracker.config import GITHUB_TOKEN

GITHUB_API = "https://api.github.com"


@dataclass
class IssueSummary:
    number: int
    title: str
    state: str
    labels: list[str]
    url: str


@dataclass
class IssueComment:
    author: str
    body: str
    created_at: str


@dataclass
class IssueDetail:
    number: int
    title: str
    state: str
    body: str
    url: str
    comments: list[IssueComment] = field(default_factory=list)


class GitHubClient(Protocol):
    def list_issues(self, repo: str, state: str) -> list[IssueSummary]: ...
    def search_issues(self, repo: str, query: str) -> list[IssueSummary]: ...
    def get_issue(self, repo: str, number: int) -> IssueDetail: ...
    def create_issue(self, repo: str, title: str, body: str) -> IssueSummary: ...
    def comment_on_issue(self, repo: str, number: int, body: str) -> str: ...


def _is_pull_request(item: dict) -> bool:
    # GitHub's "list issues" endpoint returns pull requests mixed in with real issues (a PR is
    # implemented as an issue with extra fields under the hood); a "pull_request" key is how the
    # API itself distinguishes them.
    return "pull_request" in item


def _to_summary(item: dict) -> IssueSummary:
    return IssueSummary(
        number=item["number"],
        title=item["title"],
        state=item["state"],
        labels=[label["name"] for label in item.get("labels", [])],
        url=item["html_url"],
    )


class FakeGitHubClient:
    """Canned, dependency-free stand-in for the real GitHub API -- used only when
    ISSUE_TRACKER_FAKE_GITHUB is set. Lets the true end-to-end test spawn a real server
    subprocess and exercise the full MCP tool-call wiring without a real network call."""

    def __init__(self) -> None:
        self._issues: dict[int, IssueDetail] = {
            1: IssueDetail(
                number=1,
                title="Fake issue for e2e testing",
                state="open",
                body="This issue only exists when ISSUE_TRACKER_FAKE_GITHUB is set.",
                url="https://github.com/fake/repo/issues/1",
                comments=[],
            )
        }
        self._next_number = 2

    def list_issues(self, repo: str, state: str = "open") -> list[IssueSummary]:
        return [
            IssueSummary(number=i.number, title=i.title, state=i.state, labels=[], url=i.url)
            for i in self._issues.values()
            if state == "all" or i.state == state
        ]

    def search_issues(self, repo: str, query: str) -> list[IssueSummary]:
        return [
            IssueSummary(number=i.number, title=i.title, state=i.state, labels=[], url=i.url)
            for i in self._issues.values()
            if query.lower() in i.title.lower()
        ]

    def get_issue(self, repo: str, number: int) -> IssueDetail:
        if number not in self._issues:
            raise ValueError(f"Unknown issue number in fake repo: {number}")
        return self._issues[number]

    def create_issue(self, repo: str, title: str, body: str) -> IssueSummary:
        number = self._next_number
        self._next_number += 1
        self._issues[number] = IssueDetail(
            number=number,
            title=title,
            state="open",
            body=body,
            url=f"https://github.com/fake/repo/issues/{number}",
            comments=[],
        )
        return IssueSummary(number=number, title=title, state="open", labels=[], url=self._issues[number].url)

    def comment_on_issue(self, repo: str, number: int, body: str) -> str:
        if number not in self._issues:
            raise ValueError(f"Unknown issue number in fake repo: {number}")
        self._issues[number].comments.append(
            IssueComment(author="fake-user", body=body, created_at="2026-01-01T00:00:00Z")
        )
        return f"https://github.com/fake/repo/issues/{number}#issuecomment-1"


class RealGitHubClient:
    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        # transport is a test seam: httpx.MockTransport lets tests exercise these methods'
        # header/param construction and response parsing without a real network call.
        self._client = httpx.Client(transport=transport)

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json"}
        if GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
        return headers

    def list_issues(self, repo: str, state: str = "open") -> list[IssueSummary]:
        response = self._client.get(
            f"{GITHUB_API}/repos/{repo}/issues",
            headers=self._headers(),
            params={"state": state, "per_page": 50},
        )
        response.raise_for_status()
        return [_to_summary(item) for item in response.json() if not _is_pull_request(item)]

    def search_issues(self, repo: str, query: str) -> list[IssueSummary]:
        response = self._client.get(
            f"{GITHUB_API}/search/issues",
            headers=self._headers(),
            params={"q": f"repo:{repo} type:issue {query}"},
        )
        response.raise_for_status()
        return [_to_summary(item) for item in response.json()["items"]]

    def get_issue(self, repo: str, number: int) -> IssueDetail:
        issue_response = self._client.get(
            f"{GITHUB_API}/repos/{repo}/issues/{number}", headers=self._headers()
        )
        issue_response.raise_for_status()
        issue = issue_response.json()

        comments_response = self._client.get(
            f"{GITHUB_API}/repos/{repo}/issues/{number}/comments", headers=self._headers()
        )
        comments_response.raise_for_status()
        comments = [
            IssueComment(author=c["user"]["login"], body=c["body"], created_at=c["created_at"])
            for c in comments_response.json()
        ]

        return IssueDetail(
            number=issue["number"],
            title=issue["title"],
            state=issue["state"],
            body=issue.get("body") or "",
            url=issue["html_url"],
            comments=comments,
        )

    def create_issue(self, repo: str, title: str, body: str) -> IssueSummary:
        response = self._client.post(
            f"{GITHUB_API}/repos/{repo}/issues",
            headers=self._headers(),
            json={"title": title, "body": body},
        )
        response.raise_for_status()
        return _to_summary(response.json())

    def comment_on_issue(self, repo: str, number: int, body: str) -> str:
        response = self._client.post(
            f"{GITHUB_API}/repos/{repo}/issues/{number}/comments",
            headers=self._headers(),
            json={"body": body},
        )
        response.raise_for_status()
        return str(response.json()["html_url"])
