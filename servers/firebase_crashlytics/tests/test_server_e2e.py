import json
import sys

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def _run_session(fn):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "firebase_crashlytics.server"],
        env={"CRASHLYTICS_FAKE_BACKEND": "1"},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await fn(session)


async def test_list_top_issues_over_real_protocol():
    async def scenario(session: ClientSession):
        result = await session.call_tool("list_top_issues", {"app_id": "app-1"})
        assert not result.is_error
        return result.structured_content["result"]

    issues = await _run_session(scenario)

    assert issues[0]["issue_id"] == "issue-1"
    assert issues[0]["crash_count"] == 482


async def test_get_issue_details_over_real_protocol():
    # dict-returning tools don't populate structured_content in this SDK version (confirmed
    # empirically -- only list returns do); parse the text block instead.
    async def scenario(session: ClientSession):
        result = await session.call_tool(
            "get_issue_details", {"app_id": "app-1", "issue_id": "issue-1"}
        )
        assert not result.is_error
        return json.loads(result.content[0].text)

    detail = await _run_session(scenario)

    assert detail["title"] == "NullPointerException in MainActivity"
    assert detail["is_fatal"] is True


async def test_get_issue_details_rejects_unknown_issue_with_the_real_message():
    # Regression test: MCPServer redacts a plain ValueError's message from the client by
    # default, replacing it with a generic "Error executing tool X" -- only a deliberately
    # raised ToolError's message survives. server.py wraps its tools with surface_known_errors
    # specifically so this deliberate, safe validation message actually reaches the caller.
    async def scenario(session: ClientSession):
        return await session.call_tool(
            "get_issue_details", {"app_id": "app-1", "issue_id": "no-such-issue"}
        )

    result = await _run_session(scenario)

    assert result.is_error
    assert "Unknown issue_id" in result.content[0].text
