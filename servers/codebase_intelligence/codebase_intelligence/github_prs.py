from dataclasses import dataclass
from typing import Protocol

import httpx

from codebase_intelligence.config import GITHUB_TOKEN

GITHUB_API = "https://api.github.com"


@dataclass
class PullRequestRef:
    number: int
    title: str
    url: str


class GitHubClient(Protocol):
    def get_prs_for_commit(self, github_repo: str, sha: str) -> list[PullRequestRef]: ...


class RealGitHubClient:
    def get_prs_for_commit(self, github_repo: str, sha: str) -> list[PullRequestRef]:
        headers = {"Accept": "application/vnd.github+json"}
        if GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
        response = httpx.get(
            f"{GITHUB_API}/repos/{github_repo}/commits/{sha}/pulls", headers=headers
        )
        response.raise_for_status()
        return [
            PullRequestRef(number=pr["number"], title=pr["title"], url=pr["html_url"])
            for pr in response.json()
        ]
