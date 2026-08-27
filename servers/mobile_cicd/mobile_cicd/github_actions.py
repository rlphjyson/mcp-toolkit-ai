from dataclasses import dataclass
from typing import Protocol

import httpx

from mobile_cicd.config import GITHUB_TOKEN

GITHUB_API = "https://api.github.com"


@dataclass
class WorkflowRun:
    id: int
    name: str
    status: str
    conclusion: str | None
    branch: str
    commit_sha: str
    url: str
    created_at: str


@dataclass
class WorkflowRunLogs:
    run_id: int
    summary: str


class GitHubActionsClient(Protocol):
    def list_workflow_runs(self, repo: str, branch: str | None, limit: int) -> list[WorkflowRun]: ...
    def get_workflow_run(self, repo: str, run_id: int) -> WorkflowRun: ...
    def get_run_logs_summary(self, repo: str, run_id: int) -> WorkflowRunLogs: ...
    def trigger_workflow(self, repo: str, workflow_file: str, ref: str, inputs: dict) -> dict: ...


def _to_run(item: dict) -> WorkflowRun:
    return WorkflowRun(
        id=item["id"],
        name=item["name"],
        status=item["status"],
        conclusion=item.get("conclusion"),
        branch=item["head_branch"],
        commit_sha=item["head_sha"],
        url=item["html_url"],
        created_at=item["created_at"],
    )


def _summarize_jobs(jobs: list[dict]) -> str:
    lines = []
    for job in jobs:
        lines.append(f"Job '{job['name']}': {job['status']}/{job.get('conclusion')}")
        for step in job.get("steps", []):
            lines.append(f"  - {step['name']}: {step['status']}/{step.get('conclusion')}")
    return "\n".join(lines) if lines else "No jobs found for this run."


class FakeGitHubActionsClient:
    """Canned, dependency-free stand-in for the real GitHub Actions API -- used only when
    MOBILE_CICD_FAKE_GITHUB is set. Lets the true end-to-end test spawn a real server subprocess
    and exercise the full MCP tool-call wiring without a real network call."""

    def __init__(self) -> None:
        self._runs: dict[int, WorkflowRun] = {
            1: WorkflowRun(
                id=1,
                name="Build and Test",
                status="completed",
                conclusion="success",
                branch="main",
                commit_sha="abc123",
                url="https://github.com/fake/repo/actions/runs/1",
                created_at="2026-01-01T00:00:00Z",
            )
        }
        self._next_id = 2
        self._triggered: list[dict] = []

    def list_workflow_runs(
        self, repo: str, branch: str | None = None, limit: int = 20
    ) -> list[WorkflowRun]:
        runs = [r for r in self._runs.values() if branch is None or r.branch == branch]
        return runs[:limit]

    def get_workflow_run(self, repo: str, run_id: int) -> WorkflowRun:
        if run_id not in self._runs:
            raise ValueError(f"Unknown workflow run id in fake repo: {run_id}")
        return self._runs[run_id]

    def get_run_logs_summary(self, repo: str, run_id: int) -> WorkflowRunLogs:
        if run_id not in self._runs:
            raise ValueError(f"Unknown workflow run id in fake repo: {run_id}")
        run = self._runs[run_id]
        return WorkflowRunLogs(
            run_id=run_id,
            summary=f"Job 'build': {run.status}/{run.conclusion}\n  - Checkout: completed/success",
        )

    def trigger_workflow(self, repo: str, workflow_file: str, ref: str, inputs: dict) -> dict:
        run_id = self._next_id
        self._next_id += 1
        self._runs[run_id] = WorkflowRun(
            id=run_id,
            name=workflow_file,
            status="queued",
            conclusion=None,
            branch=ref,
            commit_sha="fake-sha",
            url=f"https://github.com/fake/repo/actions/runs/{run_id}",
            created_at="2026-01-01T00:00:00Z",
        )
        self._triggered.append({"workflow_file": workflow_file, "ref": ref, "inputs": inputs})
        return {"triggered": True, "workflow_file": workflow_file, "ref": ref}


class RealGitHubActionsClient:
    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        # transport is a test seam: httpx.MockTransport lets tests exercise these methods'
        # header/param construction and response parsing without a real network call.
        self._client = httpx.Client(transport=transport)

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json"}
        if GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
        return headers

    def list_workflow_runs(
        self, repo: str, branch: str | None = None, limit: int = 20
    ) -> list[WorkflowRun]:
        params: dict[str, str | int] = {"per_page": limit}
        if branch:
            params["branch"] = branch
        response = self._client.get(
            f"{GITHUB_API}/repos/{repo}/actions/runs", headers=self._headers(), params=params
        )
        response.raise_for_status()
        return [_to_run(item) for item in response.json()["workflow_runs"]]

    def get_workflow_run(self, repo: str, run_id: int) -> WorkflowRun:
        response = self._client.get(
            f"{GITHUB_API}/repos/{repo}/actions/runs/{run_id}", headers=self._headers()
        )
        response.raise_for_status()
        return _to_run(response.json())

    def get_run_logs_summary(self, repo: str, run_id: int) -> WorkflowRunLogs:
        # GitHub's raw logs endpoint returns a zip archive of per-job log files. Downloading and
        # unzipping that archive is unnecessary for a useful summary, so this fetches the run's
        # jobs (name/status/conclusion/steps) instead and builds a plain-text summary from those.
        response = self._client.get(
            f"{GITHUB_API}/repos/{repo}/actions/runs/{run_id}/jobs", headers=self._headers()
        )
        response.raise_for_status()
        return WorkflowRunLogs(run_id=run_id, summary=_summarize_jobs(response.json()["jobs"]))

    def trigger_workflow(self, repo: str, workflow_file: str, ref: str, inputs: dict) -> dict:
        response = self._client.post(
            f"{GITHUB_API}/repos/{repo}/actions/workflows/{workflow_file}/dispatches",
            headers=self._headers(),
            json={"ref": ref, "inputs": inputs},
        )
        response.raise_for_status()
        return {"triggered": True, "workflow_file": workflow_file, "ref": ref}
