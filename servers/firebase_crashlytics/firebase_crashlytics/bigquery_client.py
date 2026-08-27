from dataclasses import dataclass
from typing import Protocol

import httpx

from firebase_crashlytics.config import (
    FIREBASE_BIGQUERY_ACCESS_TOKEN,
    FIREBASE_BIGQUERY_DATASET,
    FIREBASE_BIGQUERY_PROJECT,
)

BIGQUERY_API = "https://bigquery.googleapis.com/bigquery/v2"


@dataclass
class CrashIssue:
    issue_id: str
    title: str
    subtitle: str
    crash_count: int
    impacted_users: int
    first_seen: str
    last_seen: str
    is_fatal: bool


@dataclass
class CrashTrendPoint:
    date: str
    crash_count: int


@dataclass
class AppVersionImpact:
    version: str
    crash_count: int
    impacted_users: int


class CrashlyticsClient(Protocol):
    def list_top_issues(self, app_id: str, days: int, limit: int) -> list[CrashIssue]: ...
    def get_issue_details(self, app_id: str, issue_id: str) -> CrashIssue: ...
    def get_crash_trends(self, app_id: str, days: int) -> list[CrashTrendPoint]: ...
    def list_affected_versions(self, app_id: str, issue_id: str) -> list[AppVersionImpact]: ...


def _param(name: str, type_: str, value: str) -> dict:
    return {"name": name, "parameterType": {"type": type_}, "parameterValue": {"value": value}}


def _rows(response: dict) -> list[dict[str, str]]:
    field_names = [f["name"] for f in response.get("schema", {}).get("fields", [])]
    return [
        dict(zip(field_names, [cell.get("v") for cell in row["f"]], strict=True))
        for row in response.get("rows", [])
    ]


def _to_issue(row: dict[str, str]) -> CrashIssue:
    return CrashIssue(
        issue_id=row["issue_id"],
        title=row["title"],
        subtitle=row["subtitle"],
        crash_count=int(row["crash_count"]),
        impacted_users=int(row["impacted_users"]),
        first_seen=row["first_seen"],
        last_seen=row["last_seen"],
        is_fatal=row["is_fatal"] == "true",
    )


def _to_trend_point(row: dict[str, str]) -> CrashTrendPoint:
    return CrashTrendPoint(date=row["date"], crash_count=int(row["crash_count"]))


def _to_version_impact(row: dict[str, str]) -> AppVersionImpact:
    return AppVersionImpact(
        version=row["version"],
        crash_count=int(row["crash_count"]),
        impacted_users=int(row["impacted_users"]),
    )


class FakeCrashlyticsClient:
    """Canned, dependency-free stand-in for the real BigQuery-backed Crashlytics export --
    used only when CRASHLYTICS_FAKE_BACKEND is set. Lets the true end-to-end test spawn a real
    server subprocess and exercise the full MCP tool-call wiring without a real network call."""

    def __init__(self) -> None:
        self._issues: dict[str, CrashIssue] = {
            "issue-1": CrashIssue(
                issue_id="issue-1",
                title="NullPointerException in MainActivity",
                subtitle="com.example.app.MainActivity.onCreate",
                crash_count=482,
                impacted_users=311,
                first_seen="2026-08-01T00:00:00Z",
                last_seen="2026-08-26T00:00:00Z",
                is_fatal=True,
            ),
            "issue-2": CrashIssue(
                issue_id="issue-2",
                title="Non-fatal: network request timeout",
                subtitle="com.example.app.NetworkClient.fetch",
                crash_count=57,
                impacted_users=40,
                first_seen="2026-08-10T00:00:00Z",
                last_seen="2026-08-25T00:00:00Z",
                is_fatal=False,
            ),
        }
        self._trends = [
            CrashTrendPoint(date="2026-08-24", crash_count=120),
            CrashTrendPoint(date="2026-08-25", crash_count=95),
            CrashTrendPoint(date="2026-08-26", crash_count=140),
        ]
        self._versions: dict[str, list[AppVersionImpact]] = {
            "issue-1": [
                AppVersionImpact(version="3.2.0", crash_count=300, impacted_users=200),
                AppVersionImpact(version="3.1.0", crash_count=182, impacted_users=111),
            ],
            "issue-2": [
                AppVersionImpact(version="3.2.0", crash_count=57, impacted_users=40),
            ],
        }

    def list_top_issues(self, app_id: str, days: int = 7, limit: int = 20) -> list[CrashIssue]:
        return sorted(self._issues.values(), key=lambda i: i.crash_count, reverse=True)[:limit]

    def get_issue_details(self, app_id: str, issue_id: str) -> CrashIssue:
        if issue_id not in self._issues:
            raise ValueError(f"Unknown issue_id {issue_id!r} for app {app_id!r}")
        return self._issues[issue_id]

    def get_crash_trends(self, app_id: str, days: int = 30) -> list[CrashTrendPoint]:
        return list(self._trends)

    def list_affected_versions(self, app_id: str, issue_id: str) -> list[AppVersionImpact]:
        if issue_id not in self._versions:
            raise ValueError(f"Unknown issue_id {issue_id!r} for app {app_id!r}")
        return self._versions[issue_id]


class RealCrashlyticsClient:
    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        # transport is a test seam: httpx.MockTransport lets tests exercise these methods'
        # query/header construction and response parsing without a real network call.
        self._client = httpx.Client(transport=transport)

    def _project(self) -> str:
        if not FIREBASE_BIGQUERY_PROJECT:
            raise ValueError("FIREBASE_BIGQUERY_PROJECT is not set")
        return FIREBASE_BIGQUERY_PROJECT

    def _token(self) -> str:
        if not FIREBASE_BIGQUERY_ACCESS_TOKEN:
            raise ValueError("FIREBASE_BIGQUERY_ACCESS_TOKEN is not set")
        return FIREBASE_BIGQUERY_ACCESS_TOKEN

    def _table(self, project: str) -> str:
        # Real Crashlytics BigQuery exports use per-app, per-platform tables (e.g.
        # <dataset>.<app_id>_ANDROID / <dataset>.<app_id>_IOS) whose exact naming is
        # project-specific and varies by how each Firebase project linked BigQuery. This
        # implementation simplifies to one shared "<dataset>.crashlytics" table with app_id
        # as an ordinary WHERE clause column, rather than trying to replicate that per-project
        # schema.
        return f"`{project}.{FIREBASE_BIGQUERY_DATASET}.crashlytics`"

    def _query(self, project: str, sql: str, parameters: list[dict]) -> dict:
        response = self._client.post(
            f"{BIGQUERY_API}/projects/{project}/queries",
            headers={"Authorization": f"Bearer {self._token()}", "Content-Type": "application/json"},
            json={
                "query": sql,
                "useLegacySql": False,
                "parameterMode": "NAMED",
                "queryParameters": parameters,
            },
        )
        response.raise_for_status()
        return response.json()

    def list_top_issues(self, app_id: str, days: int = 7, limit: int = 20) -> list[CrashIssue]:
        project = self._project()
        table = self._table(project)
        sql = (
            "SELECT issue_id, title, subtitle, crash_count, impacted_users, first_seen, "
            f"last_seen, is_fatal FROM {table} WHERE app_id = @app_id AND last_seen >= "
            "TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL CAST(@days AS INT64) DAY) "
            "ORDER BY crash_count DESC LIMIT CAST(@limit AS INT64)"
        )
        response = self._query(
            project,
            sql,
            [
                _param("app_id", "STRING", app_id),
                _param("days", "INT64", str(days)),
                _param("limit", "INT64", str(limit)),
            ],
        )
        return [_to_issue(row) for row in _rows(response)]

    def get_issue_details(self, app_id: str, issue_id: str) -> CrashIssue:
        project = self._project()
        table = self._table(project)
        sql = (
            "SELECT issue_id, title, subtitle, crash_count, impacted_users, first_seen, "
            f"last_seen, is_fatal FROM {table} WHERE app_id = @app_id AND issue_id = @issue_id LIMIT 1"
        )
        response = self._query(
            project, sql, [_param("app_id", "STRING", app_id), _param("issue_id", "STRING", issue_id)]
        )
        rows = _rows(response)
        if not rows:
            raise ValueError(f"Unknown issue_id {issue_id!r} for app {app_id!r}")
        return _to_issue(rows[0])

    def get_crash_trends(self, app_id: str, days: int = 30) -> list[CrashTrendPoint]:
        project = self._project()
        table = self._table(project)
        sql = (
            f"SELECT event_date AS date, SUM(crash_count) AS crash_count FROM {table} "
            "WHERE app_id = @app_id AND event_date >= "
            "DATE_SUB(CURRENT_DATE(), INTERVAL CAST(@days AS INT64) DAY) "
            "GROUP BY date ORDER BY date"
        )
        response = self._query(
            project, sql, [_param("app_id", "STRING", app_id), _param("days", "INT64", str(days))]
        )
        return [_to_trend_point(row) for row in _rows(response)]

    def list_affected_versions(self, app_id: str, issue_id: str) -> list[AppVersionImpact]:
        project = self._project()
        table = self._table(project)
        sql = (
            f"SELECT version, crash_count, impacted_users FROM {table} "
            "WHERE app_id = @app_id AND issue_id = @issue_id ORDER BY crash_count DESC"
        )
        response = self._query(
            project, sql, [_param("app_id", "STRING", app_id), _param("issue_id", "STRING", issue_id)]
        )
        return [_to_version_impact(row) for row in _rows(response)]
