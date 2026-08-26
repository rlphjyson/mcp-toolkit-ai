import json
import sys

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def _run_session(fn):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "issue_tracker.server"],
        env={"ISSUE_TRACKER_FAKE_GITHUB": "1"},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await fn(session)


async def test_list_issues_over_real_protocol():
    async def scenario(session: ClientSession):
        result = await session.call_tool("list_issues", {"repo": "o/r"})
        assert not result.is_error
        return result.structured_content["result"]

    issues = await _run_session(scenario)

    assert issues[0]["title"] == "Fake issue for e2e testing"


async def test_create_then_get_then_comment_roundtrip_over_real_protocol():
    # dict-returning tools don't populate structured_content in this SDK version (confirmed
    # empirically -- only list returns do); parse the text block instead.
    async def scenario(session: ClientSession):
        created = await session.call_tool(
            "create_issue", {"repo": "o/r", "title": "e2e created issue", "body": "hello"}
        )
        assert not created.is_error
        number = json.loads(created.content[0].text)["number"]

        commented = await session.call_tool(
            "comment_on_issue", {"repo": "o/r", "number": number, "body": "a reply"}
        )
        assert not commented.is_error

        detail = await session.call_tool("get_issue", {"repo": "o/r", "number": number})
        assert not detail.is_error
        return json.loads(detail.content[0].text)

    detail = await _run_session(scenario)

    assert detail["title"] == "e2e created issue"
    assert detail["comments"][0]["body"] == "a reply"


async def test_get_issue_rejects_unknown_number_with_the_real_message():
    # Regression test: MCPServer redacts a plain ValueError's message from the client by
    # default, replacing it with a generic "Error executing tool X" -- only a deliberately
    # raised ToolError's message survives. server.py wraps its tools with surface_known_errors
    # specifically so this deliberate, safe validation message actually reaches the caller.
    async def scenario(session: ClientSession):
        return await session.call_tool("get_issue", {"repo": "o/r", "number": 999})

    result = await _run_session(scenario)

    assert result.is_error
    assert "Unknown issue number" in result.content[0].text
