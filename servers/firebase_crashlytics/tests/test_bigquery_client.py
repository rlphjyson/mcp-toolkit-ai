import json

import httpx
import pytest

from firebase_crashlytics.bigquery_client import FakeCrashlyticsClient, RealCrashlyticsClient

ISSUES_RESPONSE = {
    "schema": {
        "fields": [
            {"name": "issue_id", "type": "STRING"},
            {"name": "title", "type": "STRING"},
            {"name": "subtitle", "type": "STRING"},
            {"name": "crash_count", "type": "INTEGER"},
            {"name": "impacted_users", "type": "INTEGER"},
            {"name": "first_seen", "type": "TIMESTAMP"},
            {"name": "last_seen", "type": "TIMESTAMP"},
            {"name": "is_fatal", "type": "BOOLEAN"},
        ]
    },
    "rows": [
        {
            "f": [
                {"v": "issue-1"},
                {"v": "NullPointerException"},
                {"v": "MainActivity.onCreate"},
                {"v": "482"},
                {"v": "311"},
                {"v": "2026-08-01T00:00:00Z"},
                {"v": "2026-08-26T00:00:00Z"},
                {"v": "true"},
            ]
        }
    ],
}

VERSIONS_RESPONSE = {
    "schema": {
        "fields": [
            {"name": "version", "type": "STRING"},
            {"name": "crash_count", "type": "INTEGER"},
            {"name": "impacted_users", "type": "INTEGER"},
        ]
    },
    "rows": [
        {"f": [{"v": "3.2.0"}, {"v": "300"}, {"v": "200"}]},
        {"f": [{"v": "3.1.0"}, {"v": "182"}, {"v": "111"}]},
    ],
}

TRENDS_RESPONSE = {
    "schema": {"fields": [{"name": "date", "type": "DATE"}, {"name": "crash_count", "type": "INTEGER"}]},
    "rows": [
        {"f": [{"v": "2026-08-25"}, {"v": "95"}]},
        {"f": [{"v": "2026-08-26"}, {"v": "140"}]},
    ],
}

EMPTY_RESPONSE: dict = {"schema": {"fields": []}, "rows": []}


def _recording_handler(payload):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=payload, request=request)

    return handler, seen


def _configure(monkeypatch, token="test-token", project="test-project"):
    monkeypatch.setattr("firebase_crashlytics.bigquery_client.FIREBASE_BIGQUERY_ACCESS_TOKEN", token)
    monkeypatch.setattr("firebase_crashlytics.bigquery_client.FIREBASE_BIGQUERY_PROJECT", project)


def test_list_top_issues_builds_request_and_parses_response(monkeypatch):
    _configure(monkeypatch)
    handler, seen = _recording_handler(ISSUES_RESPONSE)
    client = RealCrashlyticsClient(transport=httpx.MockTransport(handler))

    issues = client.list_top_issues("app-1", days=7, limit=20)

    assert len(seen) == 1
    request = seen[0]
    assert request.method == "POST"
    assert request.url.path == "/bigquery/v2/projects/test-project/queries"
    assert request.headers["authorization"] == "Bearer test-token"

    body = json.loads(request.content)
    assert "FROM `test-project.firebase_crashlytics.crashlytics`" in body["query"]
    assert body["parameterMode"] == "NAMED"
    params = {p["name"]: p["parameterValue"]["value"] for p in body["queryParameters"]}
    assert params == {"app_id": "app-1", "days": "7", "limit": "20"}

    assert len(issues) == 1
    issue = issues[0]
    assert issue.issue_id == "issue-1"
    assert issue.title == "NullPointerException"
    assert issue.crash_count == 482
    assert issue.impacted_users == 311
    assert issue.is_fatal is True


def test_get_issue_details_parses_single_row(monkeypatch):
    _configure(monkeypatch)
    handler, seen = _recording_handler(ISSUES_RESPONSE)
    client = RealCrashlyticsClient(transport=httpx.MockTransport(handler))

    issue = client.get_issue_details("app-1", "issue-1")

    assert issue.issue_id == "issue-1"
    body = json.loads(seen[0].content)
    params = {p["name"]: p["parameterValue"]["value"] for p in body["queryParameters"]}
    assert params == {"app_id": "app-1", "issue_id": "issue-1"}


def test_get_issue_details_raises_value_error_when_no_rows(monkeypatch):
    _configure(monkeypatch)
    handler, _ = _recording_handler(EMPTY_RESPONSE)
    client = RealCrashlyticsClient(transport=httpx.MockTransport(handler))

    with pytest.raises(ValueError, match="Unknown issue_id"):
        client.get_issue_details("app-1", "no-such-issue")


def test_get_crash_trends_parses_rows(monkeypatch):
    _configure(monkeypatch)
    handler, _ = _recording_handler(TRENDS_RESPONSE)
    client = RealCrashlyticsClient(transport=httpx.MockTransport(handler))

    trends = client.get_crash_trends("app-1", days=30)

    assert [(t.date, t.crash_count) for t in trends] == [("2026-08-25", 95), ("2026-08-26", 140)]


def test_list_affected_versions_parses_rows(monkeypatch):
    _configure(monkeypatch)
    handler, _ = _recording_handler(VERSIONS_RESPONSE)
    client = RealCrashlyticsClient(transport=httpx.MockTransport(handler))

    versions = client.list_affected_versions("app-1", "issue-1")

    assert [v.version for v in versions] == ["3.2.0", "3.1.0"]
    assert versions[0].crash_count == 300
    assert versions[0].impacted_users == 200


def test_raises_on_http_error_status(monkeypatch):
    _configure(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "bad query"}, request=request)

    client = RealCrashlyticsClient(transport=httpx.MockTransport(handler))

    with pytest.raises(httpx.HTTPStatusError):
        client.list_top_issues("app-1")


def test_raises_value_error_when_access_token_missing(monkeypatch):
    _configure(monkeypatch, token=None, project="test-project")
    client = RealCrashlyticsClient()

    with pytest.raises(ValueError, match="FIREBASE_BIGQUERY_ACCESS_TOKEN"):
        client.list_top_issues("app-1")


def test_raises_value_error_when_project_missing(monkeypatch):
    _configure(monkeypatch, token="test-token", project=None)
    client = RealCrashlyticsClient()

    with pytest.raises(ValueError, match="FIREBASE_BIGQUERY_PROJECT"):
        client.list_top_issues("app-1")


def test_fake_client_list_top_issues_orders_by_crash_count():
    fake = FakeCrashlyticsClient()

    issues = fake.list_top_issues("app-1")

    assert [i.issue_id for i in issues] == ["issue-1", "issue-2"]


def test_fake_client_get_issue_details_unknown_raises_value_error():
    fake = FakeCrashlyticsClient()

    with pytest.raises(ValueError, match="Unknown issue_id"):
        fake.get_issue_details("app-1", "does-not-exist")
