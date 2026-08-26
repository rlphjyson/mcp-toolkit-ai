import json
import sys

import pytest
import sqlalchemy as sa
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


@pytest.fixture(name="db_path")
def db_path_fixture(tmp_path):
    db_path = tmp_path / "test.db"
    engine = sa.create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE items (id INTEGER PRIMARY KEY, label TEXT)"))
        conn.execute(sa.text("INSERT INTO items (label) VALUES ('widget'), ('gadget')"))
    return db_path


async def _run_session(db_path, fn):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "sql_query.server"],
        env={"SQL_QUERY_DATABASE_URL": f"sqlite:///{db_path}"},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await fn(session)


async def test_list_tables_over_real_protocol(db_path):
    async def scenario(session: ClientSession):
        result = await session.call_tool("list_tables", {})
        assert not result.is_error
        return result.structured_content["result"]

    tables = await _run_session(db_path, scenario)
    assert tables == ["items"]


async def test_run_query_over_real_protocol(db_path):
    async def scenario(session: ClientSession):
        return await session.call_tool(
            "run_query", {"sql": "SELECT label FROM items ORDER BY id"}
        )

    result = await _run_session(db_path, scenario)

    assert not result.is_error
    # dict-returning tools don't populate structured_content in this SDK version (confirmed
    # empirically -- only list returns do); parse the text block instead.
    payload = json.loads(result.content[0].text)
    assert payload["columns"] == ["label"]
    assert payload["rows"] == [["widget"], ["gadget"]]
    assert payload["truncated"] is False


async def test_run_query_rejects_destructive_sql_with_the_real_message(db_path):
    # Regression test: MCPServer redacts a plain ValueError's message from the client by
    # default, replacing it with a generic "Error executing tool X" -- only a deliberately
    # raised ToolError's message survives. server.py wraps its tools with surface_known_errors
    # specifically so this deliberate, safe validation message actually reaches the caller.
    async def scenario(session: ClientSession):
        return await session.call_tool("run_query", {"sql": "DELETE FROM items"})

    result = await _run_session(db_path, scenario)

    assert result.is_error
    assert "Only SELECT statements are allowed" in result.content[0].text
