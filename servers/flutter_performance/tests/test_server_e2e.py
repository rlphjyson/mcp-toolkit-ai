import json
import sys

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

TIMELINE = {
    "traceEvents": [
        {"name": "Frame", "ph": "X", "ts": 1_000, "dur": 10_000, "pid": 1, "tid": 1},
        {"name": "Frame", "ph": "X", "ts": 2_000, "dur": 30_000, "pid": 1, "tid": 1},
        {"name": "MyWidget.build", "ph": "X", "ts": 1_100, "dur": 500, "pid": 1, "tid": 1},
        {"name": "MyWidget.build", "ph": "X", "ts": 2_100, "dur": 500, "pid": 1, "tid": 1},
    ]
}

SIZE_TREE = {
    "n": "root",
    "children": [
        {"n": "libapp.so", "value": 4_000_000},
        {"n": "assets", "children": [{"n": "font.ttf", "value": 1_000_000}]},
    ],
}


@pytest.fixture(name="timeline_path")
def timeline_path_fixture(tmp_path):
    path = tmp_path / "timeline.json"
    path.write_text(json.dumps(TIMELINE))
    return path


@pytest.fixture(name="size_path")
def size_path_fixture(tmp_path):
    path = tmp_path / "size.json"
    path.write_text(json.dumps(SIZE_TREE))
    return path


async def _run_session(fn):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "flutter_performance.server"],
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await fn(session)


async def test_analyze_timeline_over_real_protocol(timeline_path):
    async def scenario(session: ClientSession):
        result = await session.call_tool(
            "analyze_timeline", {"timeline_json_path": str(timeline_path)}
        )
        assert not result.is_error
        return json.loads(result.content[0].text)

    summary = await _run_session(scenario)

    assert summary["frame_count"] == 2
    assert summary["jank_count"] == 1
    assert summary["jank_frame_count"] == 1
    assert len(summary["worst_frames"]) == 1
    assert summary["worst_frames"][0]["duration_ms"] == 30.0


async def test_find_jank_frames_over_real_protocol(timeline_path):
    async def scenario(session: ClientSession):
        result = await session.call_tool(
            "find_jank_frames", {"timeline_json_path": str(timeline_path), "threshold_ms": 16.67}
        )
        assert not result.is_error
        return result.structured_content["result"]

    jank = await _run_session(scenario)

    assert jank == [{"start_ts_us": 2_000, "duration_ms": 30.0}]


async def test_count_widget_rebuilds_over_real_protocol(timeline_path):
    async def scenario(session: ClientSession):
        result = await session.call_tool(
            "count_widget_rebuilds", {"timeline_json_path": str(timeline_path)}
        )
        assert not result.is_error
        return result.structured_content["result"]

    rebuilds = await _run_session(scenario)

    assert rebuilds[0] == {"name": "MyWidget", "rebuild_count": 2, "total_duration_ms": 1.0}


async def test_analyze_app_size_over_real_protocol(size_path):
    async def scenario(session: ClientSession):
        result = await session.call_tool("analyze_app_size", {"size_json_path": str(size_path)})
        assert not result.is_error
        return json.loads(result.content[0].text)

    result = await _run_session(scenario)

    assert result["total_size_bytes"] == 5_000_000
    assert result["largest_contributors"][0]["name"] == "libapp.so"


async def test_analyze_timeline_on_missing_path_surfaces_the_real_message():
    # Regression test: MCPServer redacts a plain exception's message from the client by default,
    # replacing it with a generic "Error executing tool X" -- only a deliberately raised
    # ToolError's message survives. server.py wraps its tools with surface_known_errors
    # specifically so this FileNotFoundError's specific, safe text actually reaches the caller.
    async def scenario(session: ClientSession):
        return await session.call_tool(
            "analyze_timeline", {"timeline_json_path": "/no/such/timeline.json"}
        )

    result = await _run_session(scenario)

    assert result.is_error
    assert "No such timeline file" in result.content[0].text
