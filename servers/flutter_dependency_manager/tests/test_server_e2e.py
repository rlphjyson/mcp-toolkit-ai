import json
import sys

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

PUBSPEC = """
name: e2e_sample_app
dependencies:
  flutter:
    sdk: flutter
  sample_up_to_date_pkg: ^2.3.0
  sample_outdated_pkg: ^6.0.0
  sample_discontinued_pkg: ^1.0.0
dev_dependencies:
  flutter_test:
    sdk: flutter
"""

UNKNOWN_PACKAGE_PUBSPEC = """
name: e2e_broken_app
dependencies:
  totally_unknown_pkg: ^1.0.0
"""


def _make_project(tmp_path):
    (tmp_path / "pubspec.yaml").write_text(PUBSPEC)
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    (lib_dir / "main.dart").write_text(
        "import 'package:flutter/material.dart';\n"
        "import 'package:sample_up_to_date_pkg/sample_up_to_date_pkg.dart';\n"
    )
    return tmp_path


async def _run_session(fn):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "flutter_dependency_manager.server"],
        env={"FLUTTER_DEPENDENCY_MANAGER_FAKE_PUBDEV": "1"},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await fn(session)


async def test_list_dependencies_over_real_protocol(tmp_path):
    # dict-returning tools don't populate structured_content in this SDK version (confirmed
    # empirically -- only list returns do); parse the text block instead.
    project = _make_project(tmp_path)

    async def scenario(session: ClientSession):
        result = await session.call_tool("list_dependencies", {"project_path": str(project)})
        assert not result.is_error
        return json.loads(result.content[0].text)

    result = await _run_session(scenario)

    assert result["name"] == "e2e_sample_app"
    names = {dep["name"] for dep in result["dependencies"]}
    assert "sample_up_to_date_pkg" in names


async def test_check_outdated_over_real_protocol(tmp_path):
    project = _make_project(tmp_path)

    async def scenario(session: ClientSession):
        result = await session.call_tool("check_outdated", {"project_path": str(project)})
        assert not result.is_error
        return result.structured_content["result"]

    outdated = await _run_session(scenario)

    by_name = {entry["name"]: entry for entry in outdated}
    assert by_name["sample_up_to_date_pkg"]["is_outdated"] is False
    assert by_name["sample_outdated_pkg"]["is_outdated"] is True
    assert by_name["sample_outdated_pkg"]["latest_version"] == "6.1.2"
    assert by_name["flutter"]["latest_version"] is None
    assert by_name["flutter"]["is_outdated"] is False


async def test_check_discontinued_packages_over_real_protocol(tmp_path):
    project = _make_project(tmp_path)

    async def scenario(session: ClientSession):
        result = await session.call_tool("check_discontinued_packages", {"project_path": str(project)})
        assert not result.is_error
        return result.structured_content["result"]

    discontinued = await _run_session(scenario)

    assert len(discontinued) == 1
    assert discontinued[0]["name"] == "sample_discontinued_pkg"
    assert discontinued[0]["replaced_by"] == "sample_replacement_pkg"


async def test_find_unused_dependencies_over_real_protocol(tmp_path):
    project = _make_project(tmp_path)

    async def scenario(session: ClientSession):
        result = await session.call_tool("find_unused_dependencies", {"project_path": str(project)})
        assert not result.is_error
        return result.structured_content["result"]

    unused = await _run_session(scenario)

    assert unused == ["sample_discontinued_pkg", "sample_outdated_pkg"]


async def test_check_outdated_rejects_unknown_package_with_the_real_message(tmp_path):
    # Regression test: MCPServer redacts a plain ValueError's message from the client by
    # default, replacing it with a generic "Error executing tool X" -- only a deliberately
    # raised ToolError's message survives. server.py wraps its tools with surface_known_errors
    # specifically so this deliberate, safe validation message actually reaches the caller.
    (tmp_path / "pubspec.yaml").write_text(UNKNOWN_PACKAGE_PUBSPEC)

    async def scenario(session: ClientSession):
        return await session.call_tool("check_outdated", {"project_path": str(tmp_path)})

    result = await _run_session(scenario)

    assert result.is_error
    assert "Unknown pub.dev package: totally_unknown_pkg" in result.content[0].text
