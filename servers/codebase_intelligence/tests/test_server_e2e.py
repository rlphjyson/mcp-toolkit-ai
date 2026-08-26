"""True end-to-end test: spawns the real server as a subprocess over stdio and drives it through
the actual MCP protocol, not just calling the underlying functions in-process. Uses
CODEBASE_INTELLIGENCE_FAKE_EMBEDDER so it doesn't need the real ~90MB sentence-transformers model
in CI -- the point of this test is proving the tool-call wiring works, not embedding quality.
"""

import json
import sys

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


@pytest.fixture(name="sample_repo")
def sample_repo_fixture(tmp_path):
    # A sibling of, not nested inside, the CODEBASE_INTELLIGENCE_DATA_DIR each test points at --
    # otherwise the server's own repos.json registry file would get indexed as source code.
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "auth.py").write_text(
        "def login(username, password):\n    '''Authenticate a user against the database.'''\n"
    )
    (repo_dir / "unrelated.py").write_text("def add(a, b):\n    return a + b\n")
    return repo_dir


async def _run_session(data_dir, fn):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "codebase_intelligence.server"],
        env={
            "CODEBASE_INTELLIGENCE_DATA_DIR": str(data_dir),
            "CODEBASE_INTELLIGENCE_FAKE_EMBEDDER": "1",
        },
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await fn(session)


async def test_index_and_search_over_real_protocol(tmp_path, sample_repo):
    data_dir = tmp_path / "data"

    async def scenario(session: ClientSession):
        index_result = await session.call_tool(
            "index_repository", {"repo_path": str(sample_repo)}
        )
        assert not index_result.is_error
        indexed = json.loads(index_result.content[0].text)
        assert indexed["indexed_files"] == 2

        search_result = await session.call_tool(
            "search_code", {"repo_id": indexed["repo_id"], "query": "authenticate user", "top_k": 5}
        )
        assert not search_result.is_error
        # A list-returning tool produces one TextContent block per item; structured_content
        # carries the full, typed result intact -- confirmed by inspecting a live call rather
        # than assumed, since this SDK's serialization shape for list returns isn't documented
        # anywhere obvious.
        hits = search_result.structured_content["result"]
        return indexed, hits

    indexed, hits = await _run_session(data_dir, scenario)

    assert len(hits) > 0
    assert {h["file"] for h in hits} <= {"auth.py", "unrelated.py"}


async def test_search_before_indexing_returns_a_tool_error_with_the_real_message(tmp_path):
    # Regression test: MCPServer redacts a plain ValueError's message from the client by
    # default, replacing it with a generic "Error executing tool X" -- only a deliberately
    # raised ToolError's message survives. server.py wraps its tools with surface_tool_errors
    # specifically so this deliberate, safe validation message actually reaches the caller.
    data_dir = tmp_path / "data"

    async def scenario(session: ClientSession):
        return await session.call_tool("search_code", {"repo_id": "nonexistent", "query": "x"})

    result = await _run_session(data_dir, scenario)

    assert result.is_error
    assert "Unknown repo_id 'nonexistent'" in result.content[0].text


async def test_read_file_resource_over_real_protocol(tmp_path, sample_repo):
    data_dir = tmp_path / "data"

    async def scenario(session: ClientSession):
        index_result = await session.call_tool(
            "index_repository", {"repo_path": str(sample_repo)}
        )
        indexed = json.loads(index_result.content[0].text)
        return await session.read_resource(f"code://{indexed['repo_id']}/auth.py")

    result = await _run_session(data_dir, scenario)

    assert "def login" in result.contents[0].text
