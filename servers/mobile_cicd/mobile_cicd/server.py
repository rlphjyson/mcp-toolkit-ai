import os
from collections.abc import Callable
from functools import lru_cache, wraps
from pathlib import Path
from typing import TypeVar

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from mobile_cicd.config import DEFAULT_FASTLANE_TIMEOUT_SECONDS
from mobile_cicd.fastlane_runner import FastlaneTimeoutError
from mobile_cicd.fastlane_runner import list_available_lanes as _list_available_lanes
from mobile_cicd.fastlane_runner import run_fastlane_lane as _run_fastlane_lane
from mobile_cicd.github_actions import (
    FakeGitHubActionsClient,
    GitHubActionsClient,
    RealGitHubActionsClient,
    WorkflowRun,
    WorkflowRunLogs,
)

server = MCPServer(
    "mobile-cicd",
    instructions=(
        "Mobile CI/CD bridge for Flutter release workflows. `repo` arguments are 'owner/name'; "
        "set GITHUB_TOKEN for GitHub Actions access (same pattern as issue_tracker). "
        "Scope note: a full integration across GitHub Actions, Fastlane, Firebase App "
        "Distribution, TestFlight, and Google Play in one pass would each need separate "
        "heavyweight per-vendor credential flows (App Store Connect JWT auth, Google Play "
        "service-account OAuth, Firebase App Distribution CLI/API tokens). This first pass "
        "scopes to the two pieces genuinely testable without live heavyweight OAuth: (1) GitHub "
        "Actions, since GITHUB_TOKEN is already this repo's established pattern, and (2) "
        "locally-installed Fastlane, which itself is typically how a Flutter project already "
        "talks to TestFlight/Play Console/Firebase App Distribution -- so triggering a Fastlane "
        "lane (e.g. `fastlane beta`) is the practical, already-standard way this server reaches "
        "those three vendors, rather than reimplementing each vendor API directly."
    ),
)

T = TypeVar("T")

# See issue_tracker/server.py and dev_environment/server.py for why this exists: MCPServer
# redacts a plain exception's message from the caller by default and only preserves a
# deliberately-raised ToolError's -- this surfaces safe, specific GitHub API / Fastlane error
# text instead of a generic one.
KNOWN_SAFE_ERRORS = (ValueError, httpx.HTTPStatusError, FastlaneTimeoutError)


def surface_known_errors(fn: Callable[..., T]) -> Callable[..., T]:
    @wraps(fn)
    def wrapper(*args: object, **kwargs: object) -> T:
        try:
            return fn(*args, **kwargs)
        except KNOWN_SAFE_ERRORS as exc:
            raise ToolError(str(exc)) from exc

    return wrapper


@lru_cache
def _fake_client() -> FakeGitHubActionsClient:
    # Cached so triggered-workflow state and any created run persist across tool calls within
    # one server process, matching how the real GitHub API would behave.
    return FakeGitHubActionsClient()


def _client() -> GitHubActionsClient:
    if os.environ.get("MOBILE_CICD_FAKE_GITHUB"):
        return _fake_client()
    return RealGitHubActionsClient()


def _run_dict(run: WorkflowRun) -> dict:
    return {
        "id": run.id,
        "name": run.name,
        "status": run.status,
        "conclusion": run.conclusion,
        "branch": run.branch,
        "commit_sha": run.commit_sha,
        "url": run.url,
        "created_at": run.created_at,
    }


def _logs_dict(logs: WorkflowRunLogs) -> dict:
    return {"run_id": logs.run_id, "summary": logs.summary}


@server.tool()
@surface_known_errors
def list_workflow_runs(repo: str, branch: str = "", limit: int = 20) -> list[dict]:
    """Lists recent GitHub Actions workflow runs for a repo, newest first. `branch` filters to a
    single branch when given."""
    return [_run_dict(r) for r in _client().list_workflow_runs(repo, branch or None, limit)]


@server.tool()
@surface_known_errors
def get_workflow_run(repo: str, run_id: int) -> dict:
    """One GitHub Actions workflow run's status, conclusion, and metadata."""
    return _run_dict(_client().get_workflow_run(repo, run_id))


@server.tool()
@surface_known_errors
def get_run_logs_summary(repo: str, run_id: int) -> dict:
    """A per-job/per-step summary of a workflow run's outcome, built from the run's jobs rather
    than the full raw log archive."""
    return _logs_dict(_client().get_run_logs_summary(repo, run_id))


@server.tool()
@surface_known_errors
def trigger_workflow(repo: str, workflow_file: str, ref: str = "main", inputs: dict | None = None) -> dict:
    """Dispatches a workflow_dispatch-triggered GitHub Actions workflow (e.g. 'release.yml') on a
    branch or tag."""
    return _client().trigger_workflow(repo, workflow_file, ref, inputs or {})


@server.tool()
@surface_known_errors
def list_fastlane_lanes(project_path: str) -> list[str]:
    """Lists lane names declared in a Flutter project's ios/fastlane/Fastfile and
    android/fastlane/Fastfile. Returns an empty list if no Fastfile exists."""
    return _list_available_lanes(Path(project_path))


@server.tool()
@surface_known_errors
def run_fastlane_lane(
    project_path: str, lane: str, timeout_seconds: float = DEFAULT_FASTLANE_TIMEOUT_SECONDS
) -> dict:
    """Runs a local Fastlane lane (e.g. 'beta', 'release') in a Flutter project directory and
    reports the outcome. Runs `fastlane <lane>` directly -- no shell is invoked. This is the
    practical path to TestFlight, Google Play, and Firebase App Distribution, since Fastlane
    itself is typically how a mobile project already talks to those vendors."""
    result = _run_fastlane_lane(Path(project_path), lane, timeout_seconds)
    return {
        "lane": result.lane,
        "exit_code": result.exit_code,
        "passed": result.passed,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


if __name__ == "__main__":
    server.run()
