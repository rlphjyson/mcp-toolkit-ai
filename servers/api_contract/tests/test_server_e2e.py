import json
import sys

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

SPEC_YAML = """
openapi: "3.0.0"
info:
  title: "Sample API"
  version: "1.0.0"
paths:
  /users:
    get:
      operationId: listUsers
      responses:
        "200":
          description: OK
  /users/{id}:
    get:
      operationId: getUser
      responses:
        "200":
          description: OK
    delete:
      operationId: deleteUser
      deprecated: true
      responses:
        "200":
          description: OK
components:
  schemas:
    User:
      type: object
      properties:
        id:
          type: string
        name:
          type: string
        email:
          type: string
"""

DART_MODEL = """
class User {
  final String id;
  final String name;

  User({required this.id, required this.name});
}
"""


@pytest.fixture(name="spec_file")
def spec_file_fixture(tmp_path):
    spec_file = tmp_path / "openapi.yaml"
    spec_file.write_text(SPEC_YAML)
    return spec_file


@pytest.fixture(name="flutter_project")
def flutter_project_fixture(tmp_path):
    project = tmp_path / "flutter_app"
    lib = project / "lib" / "models"
    lib.mkdir(parents=True)
    (lib / "user.dart").write_text(DART_MODEL)
    return project


async def _run_session(fn):
    params = StdioServerParameters(command=sys.executable, args=["-m", "api_contract.server"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await fn(session)


async def test_load_then_list_endpoints_over_real_protocol(spec_file):
    async def scenario(session: ClientSession):
        loaded = await session.call_tool("load_openapi_spec", {"path_or_url": str(spec_file)})
        assert not loaded.is_error
        loaded_payload = json.loads(loaded.content[0].text)

        endpoints_result = await session.call_tool(
            "list_endpoints", {"spec_id": loaded_payload["spec_id"]}
        )
        assert not endpoints_result.is_error
        return loaded_payload, endpoints_result.structured_content["result"]

    loaded_payload, endpoints = await _run_session(scenario)

    assert loaded_payload["title"] == "Sample API"
    assert loaded_payload["endpoint_count"] == 3
    assert {(e["path"], e["method"]) for e in endpoints} == {
        ("/users", "GET"),
        ("/users/{id}", "GET"),
        ("/users/{id}", "DELETE"),
    }


async def test_find_deprecated_endpoints_over_real_protocol(spec_file):
    async def scenario(session: ClientSession):
        loaded = await session.call_tool("load_openapi_spec", {"path_or_url": str(spec_file)})
        spec_id = json.loads(loaded.content[0].text)["spec_id"]

        result = await session.call_tool("find_deprecated_endpoints", {"spec_id": spec_id})
        assert not result.is_error
        return result.structured_content["result"]

    deprecated = await _run_session(scenario)

    assert [e["operation_id"] for e in deprecated] == ["deleteUser"]


async def test_compare_model_to_schema_over_real_protocol(spec_file, flutter_project):
    async def scenario(session: ClientSession):
        loaded = await session.call_tool("load_openapi_spec", {"path_or_url": str(spec_file)})
        spec_id = json.loads(loaded.content[0].text)["spec_id"]

        result = await session.call_tool(
            "compare_model_to_schema",
            {
                "spec_id": spec_id,
                "schema_name": "User",
                "project_path": str(flutter_project),
                "dart_class_name": "User",
            },
        )
        assert not result.is_error
        return json.loads(result.content[0].text)

    comparison = await _run_session(scenario)

    assert comparison["dart_fields"] == ["id", "name"]
    assert comparison["missing_in_dart_model"] == ["email"]
    assert comparison["extra_in_dart_model"] == []


async def test_compare_model_to_schema_when_dart_class_not_found_does_not_error(
    spec_file, flutter_project
):
    async def scenario(session: ClientSession):
        loaded = await session.call_tool("load_openapi_spec", {"path_or_url": str(spec_file)})
        spec_id = json.loads(loaded.content[0].text)["spec_id"]

        result = await session.call_tool(
            "compare_model_to_schema",
            {
                "spec_id": spec_id,
                "schema_name": "User",
                "project_path": str(flutter_project),
                "dart_class_name": "NoSuchModel",
            },
        )
        assert not result.is_error
        return json.loads(result.content[0].text)

    comparison = await _run_session(scenario)

    assert comparison["dart_fields"] is None
    assert comparison["missing_in_dart_model"] == []
    assert comparison["extra_in_dart_model"] == []


async def test_compare_model_to_schema_rejects_unknown_schema_with_the_real_message(
    spec_file, flutter_project
):
    # Regression test: MCPServer redacts a plain ValueError's message from the client by
    # default, replacing it with a generic "Error executing tool X" -- only a deliberately
    # raised ToolError's message survives. server.py wraps its tools with surface_known_errors
    # specifically so this deliberate, safe validation message actually reaches the caller.
    async def scenario(session: ClientSession):
        loaded = await session.call_tool("load_openapi_spec", {"path_or_url": str(spec_file)})
        spec_id = json.loads(loaded.content[0].text)["spec_id"]

        return await session.call_tool(
            "compare_model_to_schema",
            {
                "spec_id": spec_id,
                "schema_name": "DoesNotExist",
                "project_path": str(flutter_project),
                "dart_class_name": "User",
            },
        )

    result = await _run_session(scenario)

    assert result.is_error
    assert "DoesNotExist" in result.content[0].text
    assert "not found" in result.content[0].text


async def test_unknown_spec_id_surfaces_the_real_message():
    async def scenario(session: ClientSession):
        return await session.call_tool("list_endpoints", {"spec_id": "does-not-exist"})

    result = await _run_session(scenario)

    assert result.is_error
    assert "Unknown spec_id" in result.content[0].text
