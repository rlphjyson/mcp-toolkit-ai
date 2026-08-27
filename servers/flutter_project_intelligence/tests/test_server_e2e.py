import json
import sys

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


@pytest.fixture(name="project")
def project_fixture(tmp_path):
    (tmp_path / "pubspec.yaml").write_text(
        "name: my_app\n"
        "environment:\n"
        "  sdk: '>=3.0.0 <4.0.0'\n"
        "dependencies:\n"
        "  flutter:\n"
        "    sdk: flutter\n"
    )
    lib_dir = tmp_path / "lib"
    (lib_dir / "repositories").mkdir(parents=True)

    (lib_dir / "main.dart").write_text(
        "import 'home_screen.dart';\n"
        "import 'repositories/user_repository.dart';\n"
        "\n"
        "void main() {}\n"
    )
    (lib_dir / "home_screen.dart").write_text(
        "import 'package:flutter/material.dart';\n"
        "import 'repositories/user_repository.dart';\n"
        "\n"
        "class HomeScreen extends StatelessWidget {\n"
        "  @override\n"
        "  Widget build(BuildContext context) => Container();\n"
        "}\n"
    )
    (lib_dir / "repositories" / "user_repository.dart").write_text(
        "class UserRepository {\n"
        "  Future<void> save() async {}\n"
        "}\n"
    )
    return tmp_path


async def _run_session(fn):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "flutter_project_intelligence.server"],
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await fn(session)


async def test_index_then_list_widgets_and_file_dependencies_over_real_protocol(project):
    async def scenario(session: ClientSession):
        indexed = await session.call_tool("index_project", {"project_path": str(project)})
        assert not indexed.is_error
        # dict-returning tools don't populate structured_content in this SDK version (confirmed
        # empirically in issue_tracker/tests/test_server_e2e.py -- only list returns do); parse
        # the text block instead.
        summary = json.loads(indexed.content[0].text)
        assert summary["package_name"] == "my_app"
        assert summary["widgets"] == 1
        assert summary["repositories"] == 1

        widgets_result = await session.call_tool(
            "list_widgets", {"project_id": summary["project_id"]}
        )
        assert not widgets_result.is_error
        widgets = widgets_result.structured_content["result"]

        deps_result = await session.call_tool(
            "get_file_dependencies",
            {"project_id": summary["project_id"], "file_path": "lib/home_screen.dart"},
        )
        assert not deps_result.is_error
        deps = json.loads(deps_result.content[0].text)

        return widgets, deps

    widgets, deps = await _run_session(scenario)

    assert widgets == [
        {
            "name": "HomeScreen",
            "file": "lib/home_screen.dart",
            "line": 4,
            "base_class": "StatelessWidget",
        }
    ]
    assert deps["file"] == "lib/home_screen.dart"
    assert deps["imports"] == ["lib/repositories/user_repository.dart"]
    assert deps["imported_by"] == ["lib/main.dart"]


async def test_index_project_rejects_missing_pubspec_with_the_real_message(tmp_path):
    # Regression test: MCPServer redacts a plain ValueError's message from the client by
    # default, replacing it with a generic "Error executing tool X" -- only a deliberately
    # raised ToolError's message survives. server.py wraps its tools with surface_known_errors
    # specifically so this deliberate, safe validation message actually reaches the caller.
    async def scenario(session: ClientSession):
        return await session.call_tool("index_project", {"project_path": str(tmp_path)})

    result = await _run_session(scenario)

    assert result.is_error
    assert "No pubspec.yaml found" in result.content[0].text
