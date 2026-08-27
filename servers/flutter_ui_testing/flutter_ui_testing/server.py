import os
import subprocess
from collections.abc import Callable
from functools import lru_cache, wraps
from typing import TypeVar

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from flutter_ui_testing.config import DEFAULT_TEST_TIMEOUT_SECONDS
from flutter_ui_testing.device_driver import (
    AppSession,
    Device,
    DeviceDriver,
    FakeDeviceDriver,
    IntegrationTestTimeoutError,
    RealDeviceDriver,
    TestRunResult,
)

server = MCPServer(
    "flutter-ui-testing",
    instructions=(
        "Drives a running Flutter app for UI interaction and end-to-end test scenarios: list "
        "connected devices/emulators/simulators, launch/stop an app, tap/enter text/scroll, take "
        "screenshots, and run an integration_test file. Interaction tools take the session_id "
        "returned by launch_app."
    ),
)

T = TypeVar("T")

# See codebase_intelligence/server.py and sql_query/server.py for why this exists: MCPServer
# redacts a plain exception's message from the caller by default and only preserves a
# deliberately-raised ToolError's -- this surfaces safe, specific validation/subprocess/device
# error text instead of a generic one.
KNOWN_SAFE_ERRORS = (
    ValueError,
    subprocess.CalledProcessError,
    NotImplementedError,
    IntegrationTestTimeoutError,
)


def surface_known_errors(fn: Callable[..., T]) -> Callable[..., T]:
    @wraps(fn)
    def wrapper(*args: object, **kwargs: object) -> T:
        try:
            return fn(*args, **kwargs)
        except KNOWN_SAFE_ERRORS as exc:
            raise ToolError(str(exc)) from exc

    return wrapper


@lru_cache
def _fake_driver() -> FakeDeviceDriver:
    # Cached so launched sessions persist across tool calls within one server process, matching
    # how a real driver's in-process session dict would behave.
    return FakeDeviceDriver()


def _driver() -> DeviceDriver:
    if os.environ.get("FLUTTER_UI_TESTING_FAKE_DRIVER"):
        return _fake_driver()
    return RealDeviceDriver()


def _device_dict(device: Device) -> dict:
    return {
        "id": device.id,
        "name": device.name,
        "platform": device.platform,
        "is_emulator": device.is_emulator,
    }


def _session_dict(session: AppSession) -> dict:
    return {
        "session_id": session.session_id,
        "device_id": session.device_id,
        "project_path": session.project_path,
    }


def _test_result_dict(result: TestRunResult) -> dict:
    return {
        "command": result.command,
        "exit_code": result.exit_code,
        "passed": result.passed,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


@server.tool()
@surface_known_errors
def list_connected_devices() -> list[dict]:
    """Lists connected devices, emulators, and simulators available to `flutter run`."""
    return [_device_dict(d) for d in _driver().list_devices()]


@server.tool()
@surface_known_errors
def launch_app(project_path: str, device_id: str) -> dict:
    """Launches the Flutter app at `project_path` on the given device and returns a session for
    later tap/enter_text/scroll/take_screenshot calls."""
    return _session_dict(_driver().launch_app(project_path, device_id))


@server.tool()
@surface_known_errors
def stop_app(session_id: str) -> dict:
    """Stops a running app session started by launch_app."""
    _driver().stop_app(session_id)
    return {"stopped": True}


@server.tool()
@surface_known_errors
def tap(session_id: str, x: float, y: float) -> dict:
    """Taps the app's screen at (x, y) device pixel coordinates."""
    _driver().tap(session_id, x, y)
    return {"ok": True}


@server.tool()
@surface_known_errors
def enter_text(session_id: str, text: str) -> dict:
    """Enters text into the currently focused input field."""
    _driver().enter_text(session_id, text)
    return {"ok": True}


@server.tool()
@surface_known_errors
def scroll(session_id: str, dx: float, dy: float) -> dict:
    """Scrolls/swipes the app's screen by (dx, dy) device pixels."""
    _driver().scroll(session_id, dx, dy)
    return {"ok": True}


@server.tool()
@surface_known_errors
def take_screenshot(session_id: str) -> dict:
    """Captures a screenshot of the running app session and saves it as a PNG file."""
    return {"path": _driver().take_screenshot(session_id)}


@server.tool()
@surface_known_errors
def run_integration_test(
    project_path: str,
    test_file: str,
    device_id: str,
    timeout_seconds: float = DEFAULT_TEST_TIMEOUT_SECONDS,
) -> dict:
    """Runs an integration_test file (e.g. 'app_test.dart') on the given device with
    `flutter test integration_test/<test_file> -d <device_id>` and reports the outcome."""
    result = _driver().run_integration_test(project_path, test_file, device_id, timeout_seconds)
    return _test_result_dict(result)


if __name__ == "__main__":
    server.run()
