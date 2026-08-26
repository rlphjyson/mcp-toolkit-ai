import httpx
import pytest

from issue_tracker.github_issues import FakeGitHubClient, RealGitHubClient


def _handler(response_map):
    def handler(request: httpx.Request) -> httpx.Response:
        key = (request.method, request.url.path)
        if key not in response_map:
            raise AssertionError(f"Unexpected request: {key}")
        status, payload = response_map[key]
        return httpx.Response(status, json=payload, request=request)

    return handler


def test_list_issues_excludes_pull_requests():
    payload = [
        {"number": 1, "title": "Real issue", "state": "open", "labels": [], "html_url": "u1"},
        {
            "number": 2,
            "title": "A PR, not an issue",
            "state": "open",
            "labels": [],
            "html_url": "u2",
            "pull_request": {"url": "..."},
        },
    ]
    transport = httpx.MockTransport(_handler({("GET", "/repos/o/r/issues"): (200, payload)}))
    client = RealGitHubClient(transport=transport)

    issues = client.list_issues("o/r", "open")

    assert [i.number for i in issues] == [1]


def test_list_issues_parses_labels():
    payload = [
        {
            "number": 5,
            "title": "Bug",
            "state": "open",
            "labels": [{"name": "bug"}, {"name": "urgent"}],
            "html_url": "u5",
        }
    ]
    transport = httpx.MockTransport(_handler({("GET", "/repos/o/r/issues"): (200, payload)}))
    client = RealGitHubClient(transport=transport)

    issues = client.list_issues("o/r")

    assert issues[0].labels == ["bug", "urgent"]


def test_search_issues():
    payload = {"items": [{"number": 7, "title": "Found it", "state": "open", "labels": [], "html_url": "u7"}]}
    transport = httpx.MockTransport(_handler({("GET", "/search/issues"): (200, payload)}))
    client = RealGitHubClient(transport=transport)

    issues = client.search_issues("o/r", "found")

    assert [i.number for i in issues] == [7]


def test_get_issue_includes_comments():
    issue_payload = {
        "number": 3,
        "title": "Needs comments",
        "state": "open",
        "body": "body text",
        "html_url": "u3",
    }
    comments_payload = [
        {"user": {"login": "alice"}, "body": "first", "created_at": "2026-01-01T00:00:00Z"},
    ]
    transport = httpx.MockTransport(
        _handler(
            {
                ("GET", "/repos/o/r/issues/3"): (200, issue_payload),
                ("GET", "/repos/o/r/issues/3/comments"): (200, comments_payload),
            }
        )
    )
    client = RealGitHubClient(transport=transport)

    detail = client.get_issue("o/r", 3)

    assert detail.body == "body text"
    assert detail.comments[0].author == "alice"


def test_create_issue():
    payload = {"number": 9, "title": "New", "state": "open", "labels": [], "html_url": "u9"}
    transport = httpx.MockTransport(_handler({("POST", "/repos/o/r/issues"): (201, payload)}))
    client = RealGitHubClient(transport=transport)

    created = client.create_issue("o/r", "New", "body")

    assert created.number == 9


def test_comment_on_issue_returns_comment_url():
    payload = {"html_url": "https://github.com/o/r/issues/9#issuecomment-1"}
    transport = httpx.MockTransport(_handler({("POST", "/repos/o/r/issues/9/comments"): (201, payload)}))
    client = RealGitHubClient(transport=transport)

    url = client.comment_on_issue("o/r", 9, "a comment")

    assert url == "https://github.com/o/r/issues/9#issuecomment-1"


def test_raises_on_http_error_status():
    transport = httpx.MockTransport(
        _handler({("GET", "/repos/o/r/issues"): (404, {"message": "Not Found"})})
    )
    client = RealGitHubClient(transport=transport)

    with pytest.raises(httpx.HTTPStatusError):
        client.list_issues("o/r")


def test_authorization_header_included_when_token_set(monkeypatch):
    monkeypatch.setattr("issue_tracker.github_issues.GITHUB_TOKEN", "test-token")
    seen_headers = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.update(request.headers)
        return httpx.Response(200, json=[])

    client = RealGitHubClient(transport=httpx.MockTransport(handler))
    client.list_issues("o/r")

    assert seen_headers["authorization"] == "Bearer test-token"


def test_authorization_header_absent_when_no_token(monkeypatch):
    monkeypatch.setattr("issue_tracker.github_issues.GITHUB_TOKEN", None)
    seen_headers = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.update(request.headers)
        return httpx.Response(200, json=[])

    client = RealGitHubClient(transport=httpx.MockTransport(handler))
    client.list_issues("o/r")

    assert "authorization" not in seen_headers


def test_fake_client_create_then_get_then_comment_roundtrip():
    fake = FakeGitHubClient()

    created = fake.create_issue("o/r", "Fake title", "fake body")
    detail = fake.get_issue("o/r", created.number)
    fake.comment_on_issue("o/r", created.number, "a reply")
    detail_after_comment = fake.get_issue("o/r", created.number)

    assert detail.title == "Fake title"
    assert detail_after_comment.comments[0].body == "a reply"


def test_fake_client_get_unknown_issue_raises_value_error():
    fake = FakeGitHubClient()

    with pytest.raises(ValueError, match="Unknown issue number"):
        fake.get_issue("o/r", 999)
