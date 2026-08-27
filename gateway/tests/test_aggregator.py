import mcp.types as types
import pytest

from mcp_gateway.aggregator import BackendHandle, Gateway, namespaced_name, split_namespaced_name


def test_namespaced_name_joins_with_double_underscore():
    assert namespaced_name("flutterintel", "index_project") == "flutterintel__index_project"


def test_split_namespaced_name_splits_on_first_separator():
    assert split_namespaced_name("flutterintel__index_project") == ("flutterintel", "index_project")


def test_split_namespaced_name_splits_on_first_separator_only():
    # a tool name that itself happens to contain "__" still splits correctly, since the backend
    # short name is always the part before the FIRST separator.
    assert split_namespaced_name("kb__weird__tool") == ("kb", "weird__tool")


def test_split_namespaced_name_raises_value_error_without_a_separator():
    with pytest.raises(ValueError, match="not a namespaced gateway tool name"):
        split_namespaced_name("no_separator_here")


class FakeSession:
    def __init__(self, results: dict[str, types.CallToolResult]):
        self._results = results
        self.calls: list[tuple[str, dict]] = []

    async def call_tool(self, name: str, arguments: dict) -> types.CallToolResult:
        self.calls.append((name, arguments))
        if name not in self._results:
            raise RuntimeError(f"unexpected tool call: {name}")
        return self._results[name]


def _ok_result(text: str) -> types.CallToolResult:
    return types.CallToolResult(content=[types.TextContent(type="text", text=text)], is_error=False)


@pytest.fixture(name="gateway")
def gateway_fixture():
    gw = Gateway()
    session_a = FakeSession({"do_thing": _ok_result("did it")})
    session_b = FakeSession({"other_thing": _ok_result("did other")})
    gw._backends["alpha"] = BackendHandle(
        short_name="alpha",
        description="Alpha backend",
        session=session_a,  # type: ignore[arg-type]
        tools=[types.Tool(name="do_thing", description="Does a thing", input_schema={"type": "object"})],
    )
    gw._backends["beta"] = BackendHandle(
        short_name="beta",
        description="Beta backend",
        session=session_b,  # type: ignore[arg-type]
        tools=[types.Tool(name="other_thing", description="Does another", input_schema={"type": "object"})],
    )
    return gw


def test_list_all_tools_namespaces_and_labels_every_backends_tools(gateway):
    tools = gateway.list_all_tools()

    names = {t.name for t in tools}
    assert names == {"alpha__do_thing", "beta__other_thing"}
    by_name = {t.name: t for t in tools}
    assert by_name["alpha__do_thing"].description == "[alpha] Does a thing"


async def test_call_tool_routes_to_the_right_backend(gateway):
    result = await gateway.call_tool("beta__other_thing", {"x": 1})

    assert result.is_error is False
    assert result.content[0].text == "did other"
    assert gateway._backends["beta"].session.calls == [("other_thing", {"x": 1})]
    assert gateway._backends["alpha"].session.calls == []


async def test_call_tool_returns_error_result_for_unknown_backend(gateway):
    result = await gateway.call_tool("unknown__do_thing", {})

    assert result.is_error is True
    assert "Unknown gateway backend 'unknown'" in result.content[0].text


async def test_call_tool_returns_error_result_for_malformed_name(gateway):
    result = await gateway.call_tool("not_namespaced", {})

    assert result.is_error is True
    assert "not a namespaced gateway tool name" in result.content[0].text


async def test_call_tool_returns_error_result_when_backend_call_raises(gateway):
    result = await gateway.call_tool("alpha__nonexistent_tool", {})

    assert result.is_error is True
    assert "Backend 'alpha' call to 'nonexistent_tool' failed" in result.content[0].text
