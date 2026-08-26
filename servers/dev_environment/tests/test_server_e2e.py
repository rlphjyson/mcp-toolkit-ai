import json
import subprocess
import sys

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


def run_git(repo_path, *args):
    subprocess.run(["git", *args], cwd=repo_path, check=True, capture_output=True)


@pytest.fixture(name="repo")
def repo_fixture(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, "init", "-q")
    run_git(repo, "config", "user.email", "test@example.com")
    run_git(repo, "config", "user.name", "Test")
    (repo / "a.txt").write_text("a\n")
    run_git(repo, "add", "a.txt")
    run_git(repo, "commit", "-q", "-m", "initial commit")
    return repo


@pytest.fixture(name="log_dir")
def log_dir_fixture(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "app.log").write_text("line 1\nline 2\nline 3\n")
    return log_dir


async def _run_session(log_dir, fn):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "dev_environment.server"],
        env={"DEV_ENVIRONMENT_LOG_DIR": str(log_dir)},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await fn(session)


async def test_get_recent_git_commits_over_real_protocol(repo, log_dir):
    async def scenario(session: ClientSession):
        result = await session.call_tool("get_recent_git_commits", {"repo_path": str(repo)})
        assert not result.is_error
        return result.structured_content["result"]

    commits = await _run_session(log_dir, scenario)

    assert commits[0]["message"] == "initial commit"


async def test_tail_log_file_over_real_protocol(repo, log_dir):
    async def scenario(session: ClientSession):
        result = await session.call_tool("tail_log_file", {"path": "app.log", "lines": 2})
        assert not result.is_error
        return result.structured_content["result"]

    lines = await _run_session(log_dir, scenario)

    assert lines == ["line 2", "line 3"]


async def test_tail_log_file_rejects_path_traversal_with_the_real_message(repo, log_dir):
    # Regression test: MCPServer redacts a plain ValueError's message from the client by
    # default, replacing it with a generic "Error executing tool X" -- only a deliberately
    # raised ToolError's message survives. server.py wraps its tools with surface_known_errors
    # specifically so this deliberate, safe validation message actually reaches the caller.
    async def scenario(session: ClientSession):
        return await session.call_tool("tail_log_file", {"path": "../secrets.txt", "lines": 10})

    result = await _run_session(log_dir, scenario)

    assert result.is_error
    assert "escapes the allowed log directory" in result.content[0].text


async def test_run_repo_tests_over_real_protocol(repo, log_dir):
    async def scenario(session: ClientSession):
        return await session.call_tool(
            "run_repo_tests",
            {"repo_path": str(repo), "command": f'{sys.executable} -c "print(1)"'},
        )

    result = await _run_session(log_dir, scenario)

    assert not result.is_error
    payload = json.loads(result.content[0].text)
    assert payload["passed"] is True
