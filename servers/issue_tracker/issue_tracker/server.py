import os
from collections.abc import Callable
from functools import lru_cache, wraps
from typing import TypeVar

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from issue_tracker.github_issues import (
    FakeGitHubClient,
    GitHubClient,
    IssueDetail,
    IssueSummary,
    RealGitHubClient,
)

server = MCPServer(
    "issue-tracker",
    instructions=(
        "GitHub Issues bridge. `repo` arguments are 'owner/name'. Reads work without "
        "authentication at low rate limits; set GITHUB_TOKEN for higher limits and for "
        "create_issue/comment_on_issue, which need a token with repo write access."
    ),
)

T = TypeVar("T")

# See codebase_intelligence/server.py and sql_query/server.py for why this exists: MCPServer
# redacts a plain exception's message from the caller by default and only preserves a
# deliberately-raised ToolError's -- this surfaces the GitHub API's own error text (rate limit,
# 404 unknown repo, bad token) instead of a generic one.
KNOWN_SAFE_ERRORS = (ValueError, httpx.HTTPStatusError)


def surface_known_errors(fn: Callable[..., T]) -> Callable[..., T]:
    @wraps(fn)
    def wrapper(*args: object, **kwargs: object) -> T:
        try:
            return fn(*args, **kwargs)
        except KNOWN_SAFE_ERRORS as exc:
            raise ToolError(str(exc)) from exc

    return wrapper


@lru_cache
def _fake_client() -> FakeGitHubClient:
    # Cached so created issues/comments persist across tool calls within one server process,
    # matching how the real GitHub API would behave.
    return FakeGitHubClient()


def _client() -> GitHubClient:
    if os.environ.get("ISSUE_TRACKER_FAKE_GITHUB"):
        return _fake_client()
    return RealGitHubClient()


def _summary_dict(issue: IssueSummary) -> dict:
    return {
        "number": issue.number,
        "title": issue.title,
        "state": issue.state,
        "labels": issue.labels,
        "url": issue.url,
    }


def _detail_dict(issue: IssueDetail) -> dict:
    return {
        "number": issue.number,
        "title": issue.title,
        "state": issue.state,
        "body": issue.body,
        "url": issue.url,
        "comments": [
            {"author": c.author, "body": c.body, "created_at": c.created_at} for c in issue.comments
        ],
    }


@server.tool()
@surface_known_errors
def list_issues(repo: str, state: str = "open") -> list[dict]:
    """Lists issues in a repo. `state` is 'open', 'closed', or 'all'. Pull requests are excluded."""
    return [_summary_dict(i) for i in _client().list_issues(repo, state)]


@server.tool()
@surface_known_errors
def search_issues(repo: str, query: str) -> list[dict]:
    """Full-text searches issues in a repo using GitHub's search syntax."""
    return [_summary_dict(i) for i in _client().search_issues(repo, query)]


@server.tool()
@surface_known_errors
def get_issue(repo: str, number: int) -> dict:
    """One issue's title, body, and comments."""
    return _detail_dict(_client().get_issue(repo, number))


@server.tool()
@surface_known_errors
def create_issue(repo: str, title: str, body: str = "") -> dict:
    """Creates a new issue. Requires GITHUB_TOKEN with write access to the repo."""
    return _summary_dict(_client().create_issue(repo, title, body))


@server.tool()
@surface_known_errors
def comment_on_issue(repo: str, number: int, body: str) -> dict:
    """Adds a comment to an issue. Requires GITHUB_TOKEN with write access to the repo."""
    url = _client().comment_on_issue(repo, number, body)
    return {"url": url}


if __name__ == "__main__":
    server.run()
