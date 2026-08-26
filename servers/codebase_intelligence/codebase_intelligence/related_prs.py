from codebase_intelligence.git_history import CommitInfo
from codebase_intelligence.github_prs import GitHubClient, PullRequestRef


def find_related_prs(
    commits: list[CommitInfo], github_repo: str, github: GitHubClient, limit: int = 5
) -> list[PullRequestRef]:
    """GitHub has no direct 'PRs that touched this file' endpoint. This chains two real ones:
    the file's commit history (already fetched via git_history.get_file_history) tells us which
    commits touched it; 'list pull requests associated with a commit' tells us which PRs each
    commit belongs to. Dedupes by PR number since one PR can contain several of the commits."""
    seen_numbers: set[int] = set()
    related: list[PullRequestRef] = []

    for commit in commits:
        if len(related) >= limit:
            break
        for pr in github.get_prs_for_commit(github_repo, commit.sha):
            if pr.number in seen_numbers:
                continue
            seen_numbers.add(pr.number)
            related.append(pr)
            if len(related) >= limit:
                break

    return related
