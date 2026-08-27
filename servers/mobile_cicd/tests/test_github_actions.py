import httpx
import pytest

from mobile_cicd.github_actions import FakeGitHubActionsClient, RealGitHubActionsClient


def _handler(response_map):
    def handler(request: httpx.Request) -> httpx.Response:
        key = (request.method, request.url.path)
        if key not in response_map:
            raise AssertionError(f"Unexpected request: {key}")
        status, payload = response_map[key]
        if status == 204:
            return httpx.Response(status, request=request)
        return httpx.Response(status, json=payload, request=request)

    return handler


def _run_payload(**overrides):
    payload = {
        "id": 42,
        "name": "Build and Test",
        "status": "completed",
        "conclusion": "success",
        "head_branch": "main",
        "head_sha": "deadbeef",
        "html_url": "https://github.com/o/r/actions/runs/42",
        "created_at": "2026-01-01T00:00:00Z",
    }
    payload.update(overrides)
    return payload


def test_list_workflow_runs_parses_runs():
    payload = {"workflow_runs": [_run_payload()]}
    transport = httpx.MockTransport(_handler({("GET", "/repos/o/r/actions/runs"): (200, payload)}))
    client = RealGitHubActionsClient(transport=transport)

    runs = client.list_workflow_runs("o/r", None, 20)

    assert runs[0].id == 42
    assert runs[0].branch == "main"
    assert runs[0].commit_sha == "deadbeef"


def test_list_workflow_runs_sends_branch_and_limit_params():
    seen_params = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_params.update(request.url.params)
        return httpx.Response(200, json={"workflow_runs": []}, request=request)

    client = RealGitHubActionsClient(transport=httpx.MockTransport(handler))
    client.list_workflow_runs("o/r", "develop", 5)

    assert seen_params["branch"] == "develop"
    assert seen_params["per_page"] == "5"


def test_get_workflow_run():
    payload = _run_payload(id=99, conclusion=None, status="in_progress")
    transport = httpx.MockTransport(
        _handler({("GET", "/repos/o/r/actions/runs/99"): (200, payload)})
    )
    client = RealGitHubActionsClient(transport=transport)

    run = client.get_workflow_run("o/r", 99)

    assert run.id == 99
    assert run.status == "in_progress"
    assert run.conclusion is None


def test_get_run_logs_summary_builds_summary_from_jobs():
    jobs_payload = {
        "jobs": [
            {
                "name": "build",
                "status": "completed",
                "conclusion": "success",
                "steps": [
                    {"name": "Checkout", "status": "completed", "conclusion": "success"},
                    {"name": "Run tests", "status": "completed", "conclusion": "failure"},
                ],
            }
        ]
    }
    transport = httpx.MockTransport(
        _handler({("GET", "/repos/o/r/actions/runs/7/jobs"): (200, jobs_payload)})
    )
    client = RealGitHubActionsClient(transport=transport)

    logs = client.get_run_logs_summary("o/r", 7)

    assert logs.run_id == 7
    assert "build" in logs.summary
    assert "Run tests" in logs.summary
    assert "failure" in logs.summary


def test_trigger_workflow_returns_confirmation_on_204():
    transport = httpx.MockTransport(
        _handler({("POST", "/repos/o/r/actions/workflows/release.yml/dispatches"): (204, None)})
    )
    client = RealGitHubActionsClient(transport=transport)

    result = client.trigger_workflow("o/r", "release.yml", "main", {"lane": "beta"})

    assert result == {"triggered": True, "workflow_file": "release.yml", "ref": "main"}


def test_trigger_workflow_sends_ref_and_inputs():
    seen_body = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        seen_body.update(json.loads(request.content))
        return httpx.Response(204, request=request)

    client = RealGitHubActionsClient(transport=httpx.MockTransport(handler))
    client.trigger_workflow("o/r", "release.yml", "develop", {"lane": "beta"})

    assert seen_body == {"ref": "develop", "inputs": {"lane": "beta"}}


def test_raises_on_http_error_status():
    transport = httpx.MockTransport(
        _handler({("GET", "/repos/o/r/actions/runs"): (404, {"message": "Not Found"})})
    )
    client = RealGitHubActionsClient(transport=transport)

    with pytest.raises(httpx.HTTPStatusError):
        client.list_workflow_runs("o/r", None, 20)


def test_authorization_header_included_when_token_set(monkeypatch):
    monkeypatch.setattr("mobile_cicd.github_actions.GITHUB_TOKEN", "test-token")
    seen_headers = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.update(request.headers)
        return httpx.Response(200, json={"workflow_runs": []}, request=request)

    client = RealGitHubActionsClient(transport=httpx.MockTransport(handler))
    client.list_workflow_runs("o/r", None, 20)

    assert seen_headers["authorization"] == "Bearer test-token"


def test_authorization_header_absent_when_no_token(monkeypatch):
    monkeypatch.setattr("mobile_cicd.github_actions.GITHUB_TOKEN", None)
    seen_headers = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.update(request.headers)
        return httpx.Response(200, json={"workflow_runs": []}, request=request)

    client = RealGitHubActionsClient(transport=httpx.MockTransport(handler))
    client.list_workflow_runs("o/r", None, 20)

    assert "authorization" not in seen_headers


def test_fake_client_trigger_then_list_then_get_roundtrip():
    fake = FakeGitHubActionsClient()

    fake.trigger_workflow("o/r", "release.yml", "main", {"lane": "beta"})
    runs = fake.list_workflow_runs("o/r", None, 20)
    triggered_run = [r for r in runs if r.name == "release.yml"][0]
    fetched = fake.get_workflow_run("o/r", triggered_run.id)

    assert fetched.status == "queued"
    assert fetched.branch == "main"


def test_fake_client_get_unknown_run_raises_value_error():
    fake = FakeGitHubActionsClient()

    with pytest.raises(ValueError, match="Unknown workflow run id"):
        fake.get_workflow_run("o/r", 999)


def test_fake_client_list_workflow_runs_filters_by_branch():
    fake = FakeGitHubActionsClient()
    fake.trigger_workflow("o/r", "release.yml", "develop", {})

    runs = fake.list_workflow_runs("o/r", "develop", 20)

    assert all(r.branch == "develop" for r in runs)
    assert len(runs) == 1
