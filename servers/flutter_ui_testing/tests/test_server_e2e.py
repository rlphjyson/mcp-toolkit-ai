import json
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def _run_session(tmp_path, fn):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "flutter_ui_testing.server"],
        env={
            "FLUTTER_UI_TESTING_FAKE_DRIVER": "1",
            "FLUTTER_UI_TESTING_SCREENSHOT_DIR": str(tmp_path),
        },
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await fn(session)


async def test_list_connected_devices_over_real_protocol(tmp_path):
    async def scenario(session: ClientSession):
        result = await session.call_tool("list_connected_devices", {})
        assert not result.is_error
        return result.structured_content["result"]

    devices = await _run_session(tmp_path, scenario)

    platforms = {d["platform"] for d in devices}
    assert platforms == {"android", "ios"}


async def test_full_interaction_workflow_over_real_protocol(tmp_path):
    async def scenario(session: ClientSession):
        devices_result = await session.call_tool("list_connected_devices", {})
        assert not devices_result.is_error
        android_device = next(
            d for d in devices_result.structured_content["result"] if d["platform"] == "android"
        )

        launched = await session.call_tool(
            "launch_app", {"project_path": "/fake/project", "device_id": android_device["id"]}
        )
        assert not launched.is_error
        session_id = json.loads(launched.content[0].text)["session_id"]

        tap_result = await session.call_tool("tap", {"session_id": session_id, "x": 10, "y": 20})
        assert not tap_result.is_error

        text_result = await session.call_tool(
            "enter_text", {"session_id": session_id, "text": "hello world"}
        )
        assert not text_result.is_error

        scroll_result = await session.call_tool(
            "scroll", {"session_id": session_id, "dx": 0, "dy": -200}
        )
        assert not scroll_result.is_error

        screenshot_result = await session.call_tool("take_screenshot", {"session_id": session_id})
        assert not screenshot_result.is_error
        screenshot_payload = json.loads(screenshot_result.content[0].text)

        stopped = await session.call_tool("stop_app", {"session_id": session_id})
        assert not stopped.is_error

        return screenshot_payload

    screenshot_payload = await _run_session(tmp_path, scenario)

    assert Path(screenshot_payload["path"]).read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


async def test_run_integration_test_passing_scenario_over_real_protocol(tmp_path):
    async def scenario(session: ClientSession):
        return await session.call_tool(
            "run_integration_test",
            {
                "project_path": "/fake/project",
                "test_file": "app_test.dart",
                "device_id": "emulator-5554",
            },
        )

    result = await _run_session(tmp_path, scenario)

    assert not result.is_error
    payload = json.loads(result.content[0].text)
    assert payload["passed"] is True
    assert payload["exit_code"] == 0


async def test_run_integration_test_failing_scenario_over_real_protocol(tmp_path):
    async def scenario(session: ClientSession):
        return await session.call_tool(
            "run_integration_test",
            {
                "project_path": "/fake/project",
                "test_file": "login_fail_test.dart",
                "device_id": "emulator-5554",
            },
        )

    result = await _run_session(tmp_path, scenario)

    assert not result.is_error
    payload = json.loads(result.content[0].text)
    assert payload["passed"] is False
    assert payload["exit_code"] == 1


async def test_tap_with_unknown_session_id_surfaces_the_real_message(tmp_path):
    # Regression test: MCPServer redacts a plain exception's message from the client by default,
    # replacing it with a generic "Error executing tool X" -- only a deliberately raised
    # ToolError's message survives. server.py wraps its tools with surface_known_errors
    # specifically so this deliberate DeviceNotFoundError message actually reaches the caller.
    async def scenario(session: ClientSession):
        return await session.call_tool("tap", {"session_id": "no-such-session", "x": 1, "y": 1})

    result = await _run_session(tmp_path, scenario)

    assert result.is_error
    assert "Unknown session id" in result.content[0].text
