import json
import sys

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


@pytest.fixture(name="project")
def project_fixture(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "buttons.dart").write_text(
        "class MyButtons extends StatelessWidget {\n"
        "  Widget build(BuildContext context) {\n"
        "    return RaisedButton(onPressed: () {}, child: Text('go'));\n"
        "  }\n"
        "}\n"
    )
    return tmp_path


async def _run_session(fn):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "flutter_code_migration.server"],
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await fn(session)


async def test_full_mechanical_migration_flow_over_real_protocol(project):
    dart_file = project / "lib" / "buttons.dart"

    async def scenario(session: ClientSession):
        scan_result = await session.call_tool(
            "scan_for_legacy_patterns",
            {"project_path": str(project), "migration": "deprecated_widgets"},
        )
        assert not scan_result.is_error
        matches = scan_result.structured_content["result"]
        assert matches[0]["matched_text"] == "RaisedButton"

        plan_result = await session.call_tool(
            "create_migration_plan",
            {"project_path": str(project), "migration": "deprecated_widgets"},
        )
        assert not plan_result.is_error
        # create_migration_plan returns a plain dict, which -- like dev_environment's
        # run_repo_tests -- does not get a structured-output schema, so structured_content is
        # None; read the JSON text content instead.
        plan = json.loads(plan_result.content[0].text)
        assert plan["mechanical_count"] == 1

        apply_result = await session.call_tool(
            "apply_transformation",
            {"file_path": str(dart_file), "migration": "deprecated_widgets", "dry_run": False},
        )
        assert not apply_result.is_error
        payload = json.loads(apply_result.content[0].text)
        assert payload["written"] is True
        assert payload["changes_applied"] == 1
        return None

    await _run_session(scenario)

    on_disk = dart_file.read_text()
    assert "ElevatedButton(" in on_disk
    assert "RaisedButton" not in on_disk


async def test_apply_transformation_on_all_manual_migration_surfaces_real_error(project):
    dart_file = project / "lib" / "buttons.dart"

    async def scenario(session: ClientSession):
        return await session.call_tool(
            "apply_transformation",
            {"file_path": str(dart_file), "migration": "navigator_to_gorouter", "dry_run": False},
        )

    result = await _run_session(scenario)

    # Regression test: MCPServer redacts a plain ValueError's message from the client by
    # default, replacing it with a generic "Error executing tool X" -- only a deliberately
    # raised ToolError's message survives. server.py wraps its tools with surface_known_errors
    # specifically so this deliberate, safe validation message actually reaches the caller.
    assert result.is_error
    assert "no mechanical rules" in result.content[0].text


async def test_list_available_migrations_over_real_protocol(project):
    async def scenario(session: ClientSession):
        return await session.call_tool("list_available_migrations", {})

    result = await _run_session(scenario)

    assert not result.is_error
    migrations = {m["migration_id"]: m for m in result.structured_content["result"]}
    assert migrations["deprecated_widgets"]["mechanical_rule_count"] == 4
    assert migrations["navigator_to_gorouter"]["mechanical_rule_count"] == 0
    assert migrations["bloc_to_riverpod"]["mechanical_rule_count"] == 0
