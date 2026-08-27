import json
import sys

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def _run_session(fn):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mobile_cicd.server"],
        env={"MOBILE_CICD_FAKE_GITHUB": "1"},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await fn(session)


async def test_list_workflow_runs_over_real_protocol():
    async def scenario(session: ClientSession):
        result = await session.call_tool("list_workflow_runs", {"repo": "o/r"})
        assert not result.is_error
        return result.structured_content["result"]

    runs = await _run_session(scenario)

    assert runs[0]["name"] == "Build and Test"


async def test_trigger_workflow_over_real_protocol():
    # dict-returning tools don't populate structured_content in this SDK version (confirmed
    # empirically -- only list returns do); parse the text block instead.
    async def scenario(session: ClientSession):
        triggered = await session.call_tool(
            "trigger_workflow", {"repo": "o/r", "workflow_file": "release.yml", "ref": "main"}
        )
        assert not triggered.is_error
        return json.loads(triggered.content[0].text)

    result = await _run_session(scenario)

    assert result == {"triggered": True, "workflow_file": "release.yml", "ref": "main"}


async def test_list_fastlane_lanes_against_tmp_path_fixture(tmp_path):
    fastfile_dir = tmp_path / "ios" / "fastlane"
    fastfile_dir.mkdir(parents=True)
    (fastfile_dir / "Fastfile").write_text("lane :beta do\nend\n\nlane :release do\nend\n")

    async def scenario(session: ClientSession):
        result = await session.call_tool("list_fastlane_lanes", {"project_path": str(tmp_path)})
        assert not result.is_error
        return result.structured_content["result"]

    lanes = await _run_session(scenario)

    assert lanes == ["beta", "release"]


async def test_get_workflow_run_rejects_unknown_run_id_with_the_real_message():
    # Regression test: MCPServer redacts a plain ValueError's message from the client by
    # default, replacing it with a generic "Error executing tool X" -- only a deliberately
    # raised ToolError's message survives. server.py wraps its tools with surface_known_errors
    # specifically so this deliberate, safe validation message actually reaches the caller.
    async def scenario(session: ClientSession):
        return await session.call_tool("get_workflow_run", {"repo": "o/r", "run_id": 999})

    result = await _run_session(scenario)

    assert result.is_error
    assert "Unknown workflow run id" in result.content[0].text
