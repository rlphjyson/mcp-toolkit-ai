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

    lib_dir = repo / "lib" / "widgets"
    lib_dir.mkdir(parents=True)
    (lib_dir / "my_widget.dart").write_text(
        "class MyWidget {\n  void build() {\n    final x = null;\n    x!.toString();\n  }\n}\n"
    )
    run_git(repo, "add", "lib/widgets/my_widget.dart")
    run_git(repo, "commit", "-q", "-m", "add MyWidget")

    return repo


CRASH_TRACE = """\
══╡ EXCEPTION CAUGHT BY WIDGETS LIBRARY ╞══════════════════════
The following _TypeError was thrown building MyWidget(dirty):
Null check operator used on a null value

When the exception was thrown, this was the stack:
#0      MyWidget.build (package:myapp/widgets/my_widget.dart:4:6)
#1      StatelessElement.build (package:flutter/src/widgets/framework.dart:4874:28)
"""


async def _run_session(fn):
    params = StdioServerParameters(command=sys.executable, args=["-m", "flutter_crash_analyzer.server"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await fn(session)


async def test_analyze_crash_over_real_protocol_returns_blame_info(repo):
    # dict-returning tools don't populate structured_content in this SDK version (confirmed
    # empirically, see issue_tracker/tests/test_server_e2e.py -- only list returns do); parse
    # the text block instead.
    async def scenario(session: ClientSession):
        result = await session.call_tool(
            "analyze_crash",
            {
                "trace_text": CRASH_TRACE,
                "repo_path": str(repo),
                "project_package_name": "myapp",
            },
        )
        assert not result.is_error
        return json.loads(result.content[0].text)

    payload = await _run_session(scenario)

    assert payload["exception_type"] == "_TypeError"
    assert payload["message"] == "Null check operator used on a null value"
    assert payload["root_cause_tags"] == ["null_safety"]
    assert payload["likely_culprit"]["file"] == "package:myapp/widgets/my_widget.dart"
    assert payload["likely_culprit"]["line"] == 4
    assert payload["likely_culprit"]["blame"]["author"] == "Test"
    assert payload["likely_culprit"]["blame"]["summary"] == "add MyWidget"


async def test_parse_stack_trace_over_real_protocol(repo):
    async def scenario(session: ClientSession):
        result = await session.call_tool("parse_stack_trace", {"trace_text": CRASH_TRACE})
        assert not result.is_error
        return json.loads(result.content[0].text)

    payload = await _run_session(scenario)

    assert payload["exception_type"] == "_TypeError"
    assert len(payload["frames"]) == 2


async def test_tail_log_file_and_search_log_file_over_real_protocol(tmp_path):
    log_path = tmp_path / "app.log"
    log_path.write_text("info: booting\nerror: boom\ninfo: done\n")

    async def scenario(session: ClientSession):
        tail_result = await session.call_tool("tail_log_file", {"path": str(log_path), "lines": 2})
        search_result = await session.call_tool(
            "search_log_file", {"path": str(log_path), "pattern": "error.*"}
        )
        return tail_result, search_result

    tail_result, search_result = await _run_session(scenario)

    assert not tail_result.is_error
    assert tail_result.structured_content["result"] == ["error: boom", "info: done"]

    assert not search_result.is_error
    matches = search_result.structured_content["result"]
    assert matches == [{"line_number": 2, "line": "error: boom"}]


async def test_analyze_crash_on_unparseable_garbage_surfaces_specific_value_error():
    # Regression test: MCPServer redacts a plain ValueError's message from the client by
    # default, replacing it with a generic "Error executing tool X" -- only a deliberately
    # raised ToolError's message survives. server.py wraps its tools with surface_known_errors
    # specifically so this deliberate, safe validation message actually reaches the caller.
    async def scenario(session: ClientSession):
        return await session.call_tool("analyze_crash", {"trace_text": "", "repo_path": "."})

    result = await _run_session(scenario)

    assert result.is_error
    assert "trace_text is empty" in result.content[0].text


async def test_parse_stack_trace_on_garbage_prose_surfaces_specific_value_error():
    async def scenario(session: ClientSession):
        return await session.call_tool(
            "parse_stack_trace", {"trace_text": "just some prose, not a trace"}
        )

    result = await _run_session(scenario)

    assert result.is_error
    assert "Could not find" in result.content[0].text
