import json
import sys

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


@pytest.fixture(name="vault")
def vault_fixture(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "apples.md").write_text("# Apples\n\nApples are a fruit. See [[Bananas]] too.\n")
    (vault / "bananas.md").write_text("# Bananas\n\nBananas are yellow.\n")
    return vault


async def _run_session(vault, fn):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "knowledge_base.server"],
        env={"KNOWLEDGE_BASE_VAULT_DIR": str(vault)},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await fn(session)


async def test_search_notes_over_real_protocol(vault):
    async def scenario(session: ClientSession):
        result = await session.call_tool("search_notes", {"query": "yellow"})
        assert not result.is_error
        return result.structured_content["result"]

    hits = await _run_session(vault, scenario)

    assert hits == [{"path": "bananas.md", "title": "Bananas"}]


async def test_create_note_then_get_backlinks_over_real_protocol(vault):
    # dict-returning tools don't populate structured_content in this SDK version (confirmed
    # empirically -- only list returns do); parse the text block instead for create_note.
    async def scenario(session: ClientSession):
        created = await session.call_tool(
            "create_note",
            {"title": "Cherries", "content": "Cherries are red. See [[Apples]]."},
        )
        assert not created.is_error
        created_path = json.loads(created.content[0].text)["path"]

        backlinks = await session.call_tool("get_backlinks", {"path": "apples.md"})
        assert not backlinks.is_error
        return created_path, backlinks.structured_content["result"]

    created_path, backlinks = await _run_session(vault, scenario)

    assert created_path == "cherries.md"
    assert {"path": "cherries.md", "title": "Cherries"} in backlinks


async def test_read_note_resource_over_real_protocol(vault):
    async def scenario(session: ClientSession):
        return await session.read_resource("note://apples.md")

    result = await _run_session(vault, scenario)

    assert "Apples are a fruit" in result.contents[0].text


async def test_get_backlinks_rejects_unknown_note_with_the_real_message(vault):
    # Regression test: MCPServer redacts a plain ValueError's message from the client by
    # default, replacing it with a generic "Error executing tool X" -- only a deliberately
    # raised ToolError's message survives. server.py wraps its tools with surface_tool_errors
    # specifically so this deliberate, safe validation message actually reaches the caller.
    async def scenario(session: ClientSession):
        return await session.call_tool("get_backlinks", {"path": "missing.md"})

    result = await _run_session(vault, scenario)

    assert result.is_error
    assert "No such note" in result.content[0].text
