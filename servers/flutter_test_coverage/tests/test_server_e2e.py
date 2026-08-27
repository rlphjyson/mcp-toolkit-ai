import json
import sys

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

LCOV = """\
SF:lib/widgets/foo.dart
DA:1,1
DA:2,0
LF:2
LH:1
end_of_record
SF:lib/services/bar.dart
DA:1,0
DA:2,0
LF:2
LH:0
end_of_record
"""


@pytest.fixture(name="project")
def project_fixture(tmp_path):
    project = tmp_path / "project"
    (project / "coverage").mkdir(parents=True)
    (project / "coverage" / "lcov.info").write_text(LCOV)

    (project / "lib" / "widgets").mkdir(parents=True)
    (project / "lib" / "widgets" / "foo.dart").write_text("class Foo {}\n")
    (project / "lib" / "services").mkdir(parents=True)
    (project / "lib" / "services" / "bar.dart").write_text("class Bar {}\n")

    (project / "test" / "widgets").mkdir(parents=True)
    (project / "test" / "widgets" / "foo_test.dart").write_text("void main() {}\n")

    return project


async def _run_session(fn):
    params = StdioServerParameters(command=sys.executable, args=["-m", "flutter_test_coverage.server"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await fn(session)


async def test_parse_coverage_report_over_real_protocol(project):
    # parse_coverage_report returns a plain dict rather than a schema-able structured type, so
    # (like dev_environment's run_repo_tests) its result isn't populated in structured_content --
    # parse the tool's raw text content instead.
    async def scenario(session: ClientSession):
        result = await session.call_tool("parse_coverage_report", {"project_path": str(project)})
        assert not result.is_error
        return json.loads(result.content[0].text)

    summary = await _run_session(scenario)

    assert summary["total_files"] == 2
    assert summary["overall_line_coverage_percent"] == 25.0


async def test_list_low_coverage_files_over_real_protocol(project):
    async def scenario(session: ClientSession):
        result = await session.call_tool(
            "list_low_coverage_files", {"project_path": str(project), "threshold": 60.0}
        )
        assert not result.is_error
        return result.structured_content["result"]

    low = await _run_session(scenario)

    assert [entry["file"] for entry in low] == ["lib/services/bar.dart", "lib/widgets/foo.dart"]


async def test_find_missing_test_files_over_real_protocol(project):
    async def scenario(session: ClientSession):
        result = await session.call_tool("find_missing_test_files", {"project_path": str(project)})
        assert not result.is_error
        return result.structured_content["result"]

    missing = await _run_session(scenario)

    assert missing == [
        {"source_file": "lib/services/bar.dart", "expected_test_file": "services/bar_test.dart"}
    ]


async def test_parse_coverage_report_with_no_lcov_file_surfaces_the_real_message(tmp_path):
    # Regression test: MCPServer redacts a plain exception's message from the client by
    # default, replacing it with a generic "Error executing tool X" -- only a deliberately
    # raised ToolError's message survives. server.py wraps its tools with surface_known_errors
    # specifically so this FileNotFoundError's message actually reaches the caller.
    project = tmp_path / "no_coverage"
    project.mkdir()

    async def scenario(session: ClientSession):
        return await session.call_tool("parse_coverage_report", {"project_path": str(project)})

    result = await _run_session(scenario)

    assert result.is_error
    assert "run `flutter test --coverage` first" in result.content[0].text
