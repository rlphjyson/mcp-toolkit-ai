import subprocess
import sys
from pathlib import Path

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

REPO_ROOT = Path(__file__).resolve().parents[2]
GATEWAY_DIR = Path(__file__).resolve().parents[1]
KB_DIR = REPO_ROOT / "servers" / "knowledge_base"
DEVENV_DIR = REPO_ROOT / "servers" / "dev_environment"

TOML_TEMPLATE = """
[servers.kb]
description = "Personal knowledge base over local Markdown notes"
command = "python"
args = ["-m", "knowledge_base.server"]
cwd = "{kb_dir}"

[servers.kb.env]
KNOWLEDGE_BASE_VAULT_DIR = "${{KNOWLEDGE_BASE_VAULT_DIR}}"

[servers.devenv]
description = "Local dev environment awareness"
command = "python"
args = ["-m", "dev_environment.server"]
cwd = "{devenv_dir}"

[servers.gateway]
description = "The gateway's own entry -- must not be treated as a backend"
command = "python"
args = ["-m", "mcp_gateway.server"]
cwd = "{gateway_dir}"
"""


def run_git(repo_path, *args):
    subprocess.run(["git", *args], cwd=repo_path, check=True, capture_output=True)


@pytest.fixture(name="git_repo")
def git_repo_fixture(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, "init", "-q")
    run_git(repo, "config", "user.email", "test@example.com")
    run_git(repo, "config", "user.name", "Test")
    (repo / "a.txt").write_text("a\n")
    run_git(repo, "add", "a.txt")
    run_git(repo, "commit", "-q", "-m", "initial commit")
    return repo


@pytest.fixture(name="gateway_config")
def gateway_config_fixture(tmp_path):
    config_file = tmp_path / "servers.toml"
    # .as_posix(), not str(): a raw Windows path interpolated into a TOML string literal has its
    # backslashes parsed as escape sequences (e.g. "\U" starts a Unicode escape, and the next
    # four-plus characters of a real username/dir aren't valid hex -- a real, reproduced
    # TOMLDecodeError on Windows). Forward slashes parse cleanly in TOML and are still a valid
    # path on Windows.
    config_file.write_text(
        TOML_TEMPLATE.format(
            kb_dir=KB_DIR.as_posix(), devenv_dir=DEVENV_DIR.as_posix(), gateway_dir=GATEWAY_DIR.as_posix()
        )
    )
    return config_file


async def _run_session(gateway_config, vault_dir, fn):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_gateway.server"],
        cwd=GATEWAY_DIR,
        env={
            "MCP_GATEWAY_CONFIG_PATH": str(gateway_config),
            "KNOWLEDGE_BASE_VAULT_DIR": str(vault_dir),
        },
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await fn(session)


async def test_list_tools_aggregates_both_backends_under_namespaced_names(
    gateway_config, tmp_path
):
    async def scenario(session: ClientSession):
        result = await session.list_tools()
        return {t.name for t in result.tools}

    names = await _run_session(gateway_config, tmp_path / "vault", scenario)

    assert "kb__create_note" in names
    assert "devenv__get_recent_git_commits" in names
    # the gateway's own servers.toml entry must never appear as a pseudo-backend
    assert not any(n.startswith("gateway__") for n in names)


async def test_call_tool_routes_a_call_to_the_knowledge_base_backend(gateway_config, tmp_path):
    vault_dir = tmp_path / "vault"

    async def scenario(session: ClientSession):
        return await session.call_tool("kb__create_note", {"title": "Cherries", "content": "sweet"})

    result = await _run_session(gateway_config, vault_dir, scenario)

    assert not result.is_error
    assert (vault_dir / "cherries.md").is_file()


async def test_call_tool_routes_a_call_to_the_dev_environment_backend(
    gateway_config, git_repo, tmp_path
):
    async def scenario(session: ClientSession):
        return await session.call_tool(
            "devenv__get_recent_git_commits", {"repo_path": str(git_repo)}
        )

    result = await _run_session(gateway_config, tmp_path / "vault", scenario)

    assert not result.is_error
    assert "initial commit" in result.content[0].text


async def test_call_tool_returns_a_clear_error_for_an_unknown_backend(gateway_config, tmp_path):
    async def scenario(session: ClientSession):
        return await session.call_tool("nonexistent__some_tool", {})

    result = await _run_session(gateway_config, tmp_path / "vault", scenario)

    assert result.is_error
    assert "Unknown gateway backend 'nonexistent'" in result.content[0].text
