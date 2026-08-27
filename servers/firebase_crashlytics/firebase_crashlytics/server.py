import os
from collections.abc import Callable
from functools import lru_cache, wraps
from typing import TypeVar

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from firebase_crashlytics.bigquery_client import (
    AppVersionImpact,
    CrashIssue,
    CrashlyticsClient,
    CrashTrendPoint,
    FakeCrashlyticsClient,
    RealCrashlyticsClient,
)

server = MCPServer(
    "firebase-crashlytics",
    instructions=(
        "Firebase Crashlytics production crash data. Crashlytics has no public per-crash REST "
        "API; the standard way to query it programmatically is via its BigQuery export "
        "(Firebase Console -> Crashlytics -> link to BigQuery), which lands crash data in a "
        "BigQuery dataset. This server queries that export directly over BigQuery's REST API "
        "(https://bigquery.googleapis.com/bigquery/v2/projects/<project>/queries) using a "
        "bearer access token from FIREBASE_BIGQUERY_ACCESS_TOKEN (e.g. obtained via `gcloud "
        "auth print-access-token`) and a project from FIREBASE_BIGQUERY_PROJECT. It queries a "
        "single `<FIREBASE_BIGQUERY_DATASET>.crashlytics` table with `app_id` as a WHERE clause "
        "column, rather than replicating Firebase's real per-app, per-platform export table "
        "naming, which varies by project."
    ),
)

T = TypeVar("T")

# See issue_tracker/server.py: MCPServer redacts a plain exception's message from the caller by
# default and only preserves a deliberately-raised ToolError's -- this surfaces BigQuery's own
# error text (bad query, auth failure) or our own "unknown issue_id" validation instead of a
# generic one.
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
def _fake_client() -> FakeCrashlyticsClient:
    # Cached so the fake client's state is stable across calls within one server process,
    # matching how the real BigQuery export would behave.
    return FakeCrashlyticsClient()


def _client() -> CrashlyticsClient:
    if os.environ.get("CRASHLYTICS_FAKE_BACKEND"):
        return _fake_client()
    return RealCrashlyticsClient()


def _issue_dict(issue: CrashIssue) -> dict:
    return {
        "issue_id": issue.issue_id,
        "title": issue.title,
        "subtitle": issue.subtitle,
        "crash_count": issue.crash_count,
        "impacted_users": issue.impacted_users,
        "first_seen": issue.first_seen,
        "last_seen": issue.last_seen,
        "is_fatal": issue.is_fatal,
    }


def _trend_dict(point: CrashTrendPoint) -> dict:
    return {"date": point.date, "crash_count": point.crash_count}


def _version_dict(impact: AppVersionImpact) -> dict:
    return {
        "version": impact.version,
        "crash_count": impact.crash_count,
        "impacted_users": impact.impacted_users,
    }


@server.tool()
@surface_known_errors
def list_top_issues(app_id: str, days: int = 7, limit: int = 20) -> list[dict]:
    """Top crash issues for an app over the trailing `days`, ordered by crash count."""
    return [_issue_dict(i) for i in _client().list_top_issues(app_id, days, limit)]


@server.tool()
@surface_known_errors
def get_issue_details(app_id: str, issue_id: str) -> dict:
    """Details for one crash issue: title, subtitle, counts, first/last seen, fatal flag."""
    return _issue_dict(_client().get_issue_details(app_id, issue_id))


@server.tool()
@surface_known_errors
def get_crash_trends(app_id: str, days: int = 30) -> list[dict]:
    """Daily crash counts for an app over the trailing `days`."""
    return [_trend_dict(p) for p in _client().get_crash_trends(app_id, days)]


@server.tool()
@surface_known_errors
def list_affected_versions(app_id: str, issue_id: str) -> list[dict]:
    """App versions affected by one crash issue, with per-version crash and impacted-user counts."""
    return [_version_dict(v) for v in _client().list_affected_versions(app_id, issue_id)]


if __name__ == "__main__":
    server.run()
