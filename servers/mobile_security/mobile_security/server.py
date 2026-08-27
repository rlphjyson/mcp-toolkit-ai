import xml.etree.ElementTree as ET
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from plistlib import InvalidFileException
from typing import TypeVar

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from mobile_security.android_permissions import check_android_permissions as _check_android_permissions
from mobile_security.endpoint_scanner import find_insecure_endpoints as _find_insecure_endpoints
from mobile_security.ios_transport_security import (
    check_ios_transport_security as _check_ios_transport_security,
)
from mobile_security.secret_scanner import scan_for_secrets as _scan_for_secrets
from mobile_security.storage_scanner import find_unsafe_storage_usage as _find_unsafe_storage_usage

server = MCPServer(
    "mobile-security",
    instructions=(
        "Static security scan of a Flutter/Android/iOS project's own source tree: hardcoded "
        "secrets, insecure http:// endpoints, unsafe SharedPreferences usage, sensitive "
        "Android permissions, and iOS App Transport Security exceptions. Pure static file/text/"
        "XML/plist analysis -- no network access, no code execution."
    ),
)

T = TypeVar("T")

# See dev_environment/server.py for why this exists: MCPServer redacts a plain exception's
# message from the caller by default and only preserves a deliberately-raised ToolError's --
# this surfaces safe, specific parse/validation error text instead of a generic one.
KNOWN_SAFE_ERRORS = (ValueError, FileNotFoundError, ET.ParseError, InvalidFileException)


def surface_known_errors(fn: Callable[..., T]) -> Callable[..., T]:
    @wraps(fn)
    def wrapper(*args: object, **kwargs: object) -> T:
        try:
            return fn(*args, **kwargs)
        except KNOWN_SAFE_ERRORS as exc:
            raise ToolError(str(exc)) from exc

    return wrapper


@server.tool()
@surface_known_errors
def scan_for_secrets(project_path: str) -> list[dict]:
    """Scans Dart source and config files (.env/.json/.plist/.xml/.gradle/.properties) under a
    Flutter project for hardcoded secrets -- AWS/Google API keys, generic API key assignments,
    bearer tokens, private key headers, Slack tokens. Matched text is redacted in the report."""
    return _scan_for_secrets(Path(project_path))


@server.tool()
@surface_known_errors
def find_insecure_endpoints(project_path: str) -> list[dict]:
    """Scans Dart source files for hardcoded http:// URL literals, excluding localhost/loopback
    and the Android emulator-to-host alias (10.0.2.2)."""
    return _find_insecure_endpoints(Path(project_path))


@server.tool()
@surface_known_errors
def find_unsafe_storage_usage(project_path: str) -> list[dict]:
    """Scans Dart source files for SharedPreferences calls storing sensitive-looking values
    (token/password/secret/credential/apikey/session) that should instead use
    flutter_secure_storage."""
    return _find_unsafe_storage_usage(Path(project_path))


@server.tool()
@surface_known_errors
def check_android_permissions(project_path: str) -> dict:
    """Parses android/app/src/main/AndroidManifest.xml and lists all declared permissions,
    flagging a curated subset of sensitive ones (location, contacts, SMS, mic, camera,
    storage, call log, overlay windows)."""
    return _check_android_permissions(Path(project_path))


@server.tool()
@surface_known_errors
def check_ios_transport_security(project_path: str) -> dict:
    """Parses ios/Runner/Info.plist and reports whether App Transport Security is configured,
    whether NSAllowsArbitraryLoads disables HTTPS enforcement entirely, and any per-domain
    insecure HTTP load exceptions."""
    return _check_ios_transport_security(Path(project_path))


@server.tool()
@surface_known_errors
def full_security_scan(project_path: str) -> dict:
    """Runs all mobile-security scans against a project and aggregates them into one report. A
    missing AndroidManifest.xml or Info.plist (e.g. a Flutter-only or single-platform project)
    is reported as null for that section rather than raising."""
    path = Path(project_path)

    secrets = _scan_for_secrets(path)
    insecure_endpoints = _find_insecure_endpoints(path)
    unsafe_storage = _find_unsafe_storage_usage(path)

    android_permissions: dict | None
    try:
        android_permissions = _check_android_permissions(path)
    except FileNotFoundError:
        android_permissions = None

    ios_transport_security: dict | None
    try:
        ios_transport_security = _check_ios_transport_security(path)
    except FileNotFoundError:
        ios_transport_security = None

    ios_findings = 0
    if ios_transport_security is not None:
        ios_findings = len(ios_transport_security["insecure_domain_exceptions"]) + (
            1 if ios_transport_security["allows_arbitrary_loads"] else 0
        )

    total_findings = (
        len(secrets)
        + len(insecure_endpoints)
        + len(unsafe_storage)
        + len(android_permissions["flagged_permissions"] if android_permissions else [])
        + ios_findings
    )

    return {
        "secrets": secrets,
        "insecure_endpoints": insecure_endpoints,
        "unsafe_storage": unsafe_storage,
        "android_permissions": android_permissions,
        "ios_transport_security": ios_transport_security,
        "summary": {"total_findings": total_findings},
    }


if __name__ == "__main__":
    server.run()
