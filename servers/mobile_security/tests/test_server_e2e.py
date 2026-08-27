import json
import plistlib
import sys

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

MANIFEST_XML = """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-permission android:name="android.permission.INTERNET"/>
    <uses-permission android:name="android.permission.CAMERA"/>
</manifest>
"""


@pytest.fixture(name="project")
def project_fixture(tmp_path):
    project = tmp_path / "app"
    lib = project / "lib"
    lib.mkdir(parents=True)
    (lib / "api.dart").write_text(
        "import 'package:shared_preferences/shared_preferences.dart';\n"
        "const awsKey = \"AKIAABCDEFGHIJKLMNOP\";\n"
        "final url = 'http://example.com/api';\n"
        "prefs.setString('auth_token', token);\n"
    )

    manifest_dir = project / "android" / "app" / "src" / "main"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "AndroidManifest.xml").write_text(MANIFEST_XML)

    runner_dir = project / "ios" / "Runner"
    runner_dir.mkdir(parents=True)
    with (runner_dir / "Info.plist").open("wb") as f:
        plistlib.dump({"NSAppTransportSecurity": {"NSAllowsArbitraryLoads": True}}, f)

    return project


async def _run_session(fn):
    params = StdioServerParameters(command=sys.executable, args=["-m", "mobile_security.server"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await fn(session)


async def test_full_security_scan_over_real_protocol(project):
    async def scenario(session: ClientSession):
        result = await session.call_tool("full_security_scan", {"project_path": str(project)})
        assert not result.is_error
        return json.loads(result.content[0].text)

    report = await _run_session(scenario)

    assert len(report["secrets"]) == 1
    assert len(report["insecure_endpoints"]) == 1
    assert len(report["unsafe_storage"]) == 1
    assert report["android_permissions"]["flagged_permissions"] == ["android.permission.CAMERA"]
    assert report["ios_transport_security"]["allows_arbitrary_loads"] is True
    assert report["summary"]["total_findings"] == 5


async def test_full_security_scan_reports_null_for_missing_manifest_and_plist(tmp_path):
    project = tmp_path / "flutter_only"
    lib = project / "lib"
    lib.mkdir(parents=True)
    (lib / "main.dart").write_text("void main() {}\n")

    async def scenario(session: ClientSession):
        result = await session.call_tool("full_security_scan", {"project_path": str(project)})
        assert not result.is_error
        return json.loads(result.content[0].text)

    report = await _run_session(scenario)

    assert report["android_permissions"] is None
    assert report["ios_transport_security"] is None
    assert report["summary"]["total_findings"] == 0


async def test_check_android_permissions_surfaces_real_error_message(tmp_path):
    # Regression test: MCPServer redacts a plain exception's message from the client by default
    # -- only a deliberately raised ToolError's message survives. server.py wraps its tools with
    # surface_known_errors specifically so this FileNotFoundError message reaches the caller.
    project = tmp_path / "no_android"
    project.mkdir()

    async def scenario(session: ClientSession):
        return await session.call_tool(
            "check_android_permissions", {"project_path": str(project)}
        )

    result = await _run_session(scenario)

    assert result.is_error
    assert "AndroidManifest.xml not found" in result.content[0].text
