from dataclasses import dataclass
from typing import Protocol

import httpx

from flutter_dependency_manager.config import PUB_DEV_API_BASE

_NON_HOSTED_PREFIXES = ("git:", "path:", "sdk:")
_CONSTRAINT_PREFIXES = (">=", "^", "~", ">", "=")


@dataclass
class PackageInfo:
    name: str
    current_constraint: str
    latest_version: str | None
    is_outdated: bool
    is_discontinued: bool
    replaced_by: str | None


class PubDevClient(Protocol):
    def get_package_info(self, name: str) -> dict: ...


def _lower_bound(constraint: str) -> str:
    token = constraint.strip().split()[0] if constraint.strip() else constraint
    for prefix in _CONSTRAINT_PREFIXES:
        if token.startswith(prefix):
            return token[len(prefix) :]
    return token


def _parse_version_tuple(version: str) -> tuple[int, ...] | None:
    core = version.split("+")[0].split("-")[0]
    try:
        return tuple(int(part) for part in core.split("."))
    except ValueError:
        return None


def _is_outdated(current_constraint: str, latest_version: str) -> bool:
    if current_constraint.startswith(_NON_HOSTED_PREFIXES):
        return False
    if current_constraint == "any" or not latest_version:
        return False

    lower_tuple = _parse_version_tuple(_lower_bound(current_constraint))
    latest_tuple = _parse_version_tuple(latest_version)
    if lower_tuple is None or latest_tuple is None:
        return False

    return latest_tuple > lower_tuple


def _to_package_info(name: str, current_constraint: str, raw: dict) -> PackageInfo:
    latest = raw.get("latest") or {}
    latest_version = latest.get("version")
    is_discontinued = bool(raw.get("isDiscontinued", False))
    replaced_by = raw.get("replacedBy")
    is_outdated = _is_outdated(current_constraint, latest_version) if latest_version else False

    return PackageInfo(
        name=name,
        current_constraint=current_constraint,
        latest_version=latest_version,
        is_outdated=is_outdated,
        is_discontinued=is_discontinued,
        replaced_by=replaced_by,
    )


class FakePubDevClient:
    """Canned, dependency-free stand-in for the real pub.dev API -- used only when
    FLUTTER_DEPENDENCY_MANAGER_FAKE_PUBDEV is set. Lets the true end-to-end test spawn a real
    server subprocess and exercise the full MCP tool-call wiring without a real network call."""

    _PACKAGES: dict[str, dict] = {
        "sample_up_to_date_pkg": {
            "name": "sample_up_to_date_pkg",
            "latest": {"version": "2.3.0", "pubspec": {"name": "sample_up_to_date_pkg", "version": "2.3.0"}},
            "isDiscontinued": False,
            "replacedBy": None,
        },
        "sample_outdated_pkg": {
            "name": "sample_outdated_pkg",
            "latest": {"version": "6.1.2", "pubspec": {"name": "sample_outdated_pkg", "version": "6.1.2"}},
            "isDiscontinued": False,
            "replacedBy": None,
        },
        "sample_discontinued_pkg": {
            "name": "sample_discontinued_pkg",
            "latest": {
                "version": "1.0.0",
                "pubspec": {"name": "sample_discontinued_pkg", "version": "1.0.0"},
            },
            "isDiscontinued": True,
            "replacedBy": "sample_replacement_pkg",
        },
    }

    def get_package_info(self, name: str) -> dict:
        if name not in self._PACKAGES:
            raise ValueError(f"Unknown pub.dev package (fake): {name}")
        return self._PACKAGES[name]


class RealPubDevClient:
    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        # transport is a test seam: httpx.MockTransport lets tests exercise the URL built and
        # response parsing without a real network call.
        self._client = httpx.Client(transport=transport)

    def get_package_info(self, name: str) -> dict:
        response = self._client.get(f"{PUB_DEV_API_BASE}/packages/{name}")
        response.raise_for_status()
        return dict(response.json())
