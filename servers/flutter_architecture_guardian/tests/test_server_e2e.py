"""True end-to-end test: spawns the real server as a subprocess over stdio and drives it through
the actual MCP protocol, not just calling the underlying functions in-process.
"""

import json
import sys

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


@pytest.fixture(name="project")
def project_fixture(tmp_path):
    (tmp_path / "pubspec.yaml").write_text("name: sample_app\ndescription: test\n")
    lib = tmp_path / "lib"
    (lib / "presentation").mkdir(parents=True)
    (lib / "domain" / "entities").mkdir(parents=True)
    (lib / "data").mkdir(parents=True)

    (lib / "domain" / "entities" / "user.dart").write_text("class User {}\n")
    (lib / "data" / "user_repository_impl.dart").write_text(
        "import '../domain/entities/user.dart';\nclass UserRepositoryImpl {}\n"
    )
    # Deliberate violation: presentation reaching straight into data instead of through domain.
    (lib / "presentation" / "home_screen.dart").write_text(
        "import 'package:sample_app/domain/entities/user.dart';\n"
        "import '../data/user_repository_impl.dart';\n"
        "class HomeScreen {}\n"
    )
    return tmp_path


async def _run_session(fn):
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "flutter_architecture_guardian.server"]
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await fn(session)


async def test_analyze_architecture_reports_the_deliberate_violation_over_real_protocol(project):
    async def scenario(session: ClientSession):
        result = await session.call_tool("analyze_architecture", {"project_path": str(project)})
        assert not result.is_error
        return json.loads(result.content[0].text)

    report = await _run_session(scenario)

    assert report["style"] == "clean"
    assert report["files_scanned"] == 3
    assert report["violation_count"] == 1
    assert report["violations"][0]["rule"] == "presentation_imports_data"


async def test_invalid_style_surfaces_the_real_value_error_message(project):
    # Regression test: MCPServer redacts a plain ValueError's message from the client by
    # default, replacing it with a generic "Error executing tool X" -- only a deliberately
    # raised ToolError's message survives. server.py wraps its tools with surface_known_errors
    # specifically so this deliberate, safe validation message actually reaches the caller.
    async def scenario(session: ClientSession):
        return await session.call_tool(
            "analyze_architecture", {"project_path": str(project), "style": "mvc"}
        )

    result = await _run_session(scenario)

    assert result.is_error
    assert "Unknown style 'mvc'" in result.content[0].text
