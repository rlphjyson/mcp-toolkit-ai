import base64
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from flutter_ui_testing.config import SCREENSHOT_DIR


class DeviceNotFoundError(ValueError):
    pass


class IntegrationTestTimeoutError(Exception):
    pass


@dataclass
class Device:
    id: str
    name: str
    platform: str
    is_emulator: bool


@dataclass
class AppSession:
    session_id: str
    device_id: str
    project_path: str


@dataclass
class TestRunResult:
    command: str
    exit_code: int
    passed: bool
    stdout: str
    stderr: str


class DeviceDriver(Protocol):
    def list_devices(self) -> list[Device]: ...
    def launch_app(self, project_path: str, device_id: str) -> AppSession: ...
    def stop_app(self, session_id: str) -> None: ...
    def tap(self, session_id: str, x: float, y: float) -> None: ...
    def enter_text(self, session_id: str, text: str) -> None: ...
    def scroll(self, session_id: str, dx: float, dy: float) -> None: ...
    def take_screenshot(self, session_id: str) -> str: ...
    def run_integration_test(
        self, project_path: str, test_file: str, device_id: str, timeout_seconds: float
    ) -> TestRunResult: ...


def _platform_from_target(target_platform: str) -> str:
    # `flutter devices --machine` reports targets like "android-arm64", "ios",
    # "darwin-x64" (macOS desktop), "web-javascript", "windows-x64", "linux-x64". Device.platform
    # only distinguishes the three kinds this server can actually drive; anything that isn't
    # clearly android/ios collapses to "web" since desktop targets get the same "no input CLI"
    # treatment as a browser tab.
    if target_platform.startswith("android"):
        return "android"
    if target_platform.startswith("ios"):
        return "ios"
    return "web"


def parse_devices_json(raw: str) -> list[Device]:
    try:
        items = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Could not parse `flutter devices --machine` output: {exc}") from exc

    return [
        Device(
            id=item["id"],
            name=item["name"],
            platform=_platform_from_target(item.get("targetPlatform", "")),
            is_emulator=bool(item.get("emulator", False)),
        )
        for item in items
    ]


@dataclass
class _Session:
    session_id: str
    device_id: str
    project_path: str
    platform: str
    process: "subprocess.Popen[str] | None"


class RealDeviceDriver:
    """Wraps the real `flutter`, `adb`, and `xcrun simctl` CLIs as subprocesses.

    This is a best-effort wrapper, not a full test-automation harness: `launch_app` starts
    `flutter run` as a background process and tracks it by PID, but does not attach to its Dart
    VM service, so it cannot wait for the app to actually be ready or read widget state back.
    Production-grade interactive driving would use the Dart VM service / `flutter_driver`
    (or `integration_test`'s own instrumentation) instead -- that's out of scope for this pass.

    Input synthesis is honest about what each platform's CLI actually supports: adb genuinely
    exposes `input tap/text/swipe`, so Android sessions get real taps/text/scrolls. Apple's
    `xcrun simctl` has no public equivalent -- it manages simulator lifecycle (boot, install,
    screenshot) but not touch/keyboard event injection -- so iOS sessions raise NotImplementedError
    for tap/enter_text/scroll, same as web. `xcrun simctl io <udid> screenshot` is real and used
    for iOS screenshots.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, _Session] = {}

    def list_devices(self) -> list[Device]:
        try:
            process = subprocess.run(
                ["flutter", "devices", "--machine"],
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
            )
        except FileNotFoundError as exc:
            raise ValueError("`flutter` CLI not found on PATH") from exc
        except subprocess.CalledProcessError as exc:
            raise ValueError(f"`flutter devices` failed: {exc.stderr}") from exc
        return parse_devices_json(process.stdout)

    def _find_device(self, device_id: str) -> Device:
        for device in self.list_devices():
            if device.id == device_id:
                return device
        raise DeviceNotFoundError(f"Unknown device id: {device_id}")

    def _get_session(self, session_id: str) -> _Session:
        if session_id not in self._sessions:
            raise DeviceNotFoundError(f"Unknown session id: {session_id}")
        return self._sessions[session_id]

    def launch_app(self, project_path: str, device_id: str) -> AppSession:
        device = self._find_device(device_id)
        process = subprocess.Popen(
            ["flutter", "run", "-d", device_id, "--no-hot", "-t", "lib/main.dart"],
            cwd=project_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        session_id = uuid4().hex
        self._sessions[session_id] = _Session(
            session_id=session_id,
            device_id=device_id,
            project_path=project_path,
            platform=device.platform,
            process=process,
        )
        return AppSession(session_id=session_id, device_id=device_id, project_path=project_path)

    def stop_app(self, session_id: str) -> None:
        session = self._get_session(session_id)
        if session.process is not None and session.process.poll() is None:
            session.process.terminate()
            try:
                session.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                session.process.kill()
        del self._sessions[session_id]

    def tap(self, session_id: str, x: float, y: float) -> None:
        session = self._get_session(session_id)
        if session.platform == "android":
            subprocess.run(
                ["adb", "-s", session.device_id, "shell", "input", "tap", str(int(x)), str(int(y))],
                check=True,
                timeout=10,
                capture_output=True,
            )
        elif session.platform == "ios":
            raise NotImplementedError(
                "xcrun simctl has no public tap-injection equivalent to `adb shell input tap`"
            )
        else:
            raise NotImplementedError("Web sessions have no CLI input-injection equivalent")

    def enter_text(self, session_id: str, text: str) -> None:
        session = self._get_session(session_id)
        if session.platform == "android":
            subprocess.run(
                ["adb", "-s", session.device_id, "shell", "input", "text", text],
                check=True,
                timeout=10,
                capture_output=True,
            )
        elif session.platform == "ios":
            raise NotImplementedError(
                "xcrun simctl has no public text-injection equivalent to `adb shell input text`"
            )
        else:
            raise NotImplementedError("Web sessions have no CLI input-injection equivalent")

    def scroll(self, session_id: str, dx: float, dy: float) -> None:
        session = self._get_session(session_id)
        if session.platform == "android":
            start_x, start_y = 0, 0
            end_x, end_y = int(dx), int(dy)
            subprocess.run(
                [
                    "adb", "-s", session.device_id, "shell", "input", "swipe",
                    str(start_x), str(start_y), str(end_x), str(end_y),
                ],
                check=True,
                timeout=10,
                capture_output=True,
            )
        elif session.platform == "ios":
            raise NotImplementedError(
                "xcrun simctl has no public swipe-injection equivalent to `adb shell input swipe`"
            )
        else:
            raise NotImplementedError("Web sessions have no CLI input-injection equivalent")

    def take_screenshot(self, session_id: str) -> str:
        session = self._get_session(session_id)
        out_path = Path(SCREENSHOT_DIR) / f"{session_id}-{uuid4().hex}.png"
        if session.platform == "android":
            with out_path.open("wb") as f:
                subprocess.run(
                    ["adb", "-s", session.device_id, "exec-out", "screencap", "-p"],
                    stdout=f,
                    check=True,
                    timeout=30,
                )
        elif session.platform == "ios":
            subprocess.run(
                ["xcrun", "simctl", "io", session.device_id, "screenshot", str(out_path)],
                check=True,
                timeout=30,
                capture_output=True,
            )
        else:
            raise NotImplementedError("Web sessions have no CLI screenshot equivalent")
        return str(out_path)

    def run_integration_test(
        self, project_path: str, test_file: str, device_id: str, timeout_seconds: float
    ) -> TestRunResult:
        args = ["flutter", "test", f"integration_test/{test_file}", "-d", device_id]
        try:
            process = subprocess.run(
                args,
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise IntegrationTestTimeoutError(
                f"Integration test timed out after {timeout_seconds}s: {test_file}"
            ) from exc
        except FileNotFoundError as exc:
            raise ValueError("`flutter` CLI not found on PATH") from exc

        return TestRunResult(
            command=" ".join(args),
            exit_code=process.returncode,
            passed=process.returncode == 0,
            stdout=process.stdout,
            stderr=process.stderr,
        )


# Smallest possible valid PNG: a 1x1 transparent pixel. FakeDeviceDriver writes this to disk so
# take_screenshot's contract (a real, readable PNG file path) holds under test without a device.
_PLACEHOLDER_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class FakeDeviceDriver:
    """Deterministic, dependency-free stand-in for a real device/emulator -- used only when
    FLUTTER_UI_TESTING_FAKE_DRIVER is set. Lets the true end-to-end test spawn a real server
    subprocess and exercise the full MCP tool-call wiring without a real device, emulator, or
    the Flutter SDK installed. `calls` is a call log tests can assert against."""

    def __init__(self) -> None:
        self._devices = [
            Device(
                id="emulator-5554", name="Fake Android Emulator", platform="android", is_emulator=True
            ),
            Device(
                id="00000000-FAKE0000IOSSIM0", name="Fake iOS Simulator", platform="ios", is_emulator=True
            ),
        ]
        self._sessions: dict[str, AppSession] = {}
        self._next_session = 1
        self.calls: list[tuple] = []

    def list_devices(self) -> list[Device]:
        return list(self._devices)

    def _find_device(self, device_id: str) -> Device:
        for device in self._devices:
            if device.id == device_id:
                return device
        raise DeviceNotFoundError(f"Unknown device id: {device_id}")

    def _get_session(self, session_id: str) -> AppSession:
        if session_id not in self._sessions:
            raise DeviceNotFoundError(f"Unknown session id: {session_id}")
        return self._sessions[session_id]

    def launch_app(self, project_path: str, device_id: str) -> AppSession:
        self._find_device(device_id)
        session_id = f"fake-session-{self._next_session}"
        self._next_session += 1
        session = AppSession(session_id=session_id, device_id=device_id, project_path=project_path)
        self._sessions[session_id] = session
        self.calls.append(("launch_app", project_path, device_id))
        return session

    def stop_app(self, session_id: str) -> None:
        self._get_session(session_id)
        del self._sessions[session_id]
        self.calls.append(("stop_app", session_id))

    def tap(self, session_id: str, x: float, y: float) -> None:
        self._get_session(session_id)
        self.calls.append(("tap", session_id, x, y))

    def enter_text(self, session_id: str, text: str) -> None:
        self._get_session(session_id)
        self.calls.append(("enter_text", session_id, text))

    def scroll(self, session_id: str, dx: float, dy: float) -> None:
        self._get_session(session_id)
        self.calls.append(("scroll", session_id, dx, dy))

    def take_screenshot(self, session_id: str) -> str:
        self._get_session(session_id)
        out_path = Path(SCREENSHOT_DIR) / f"{session_id}-{uuid4().hex}.png"
        out_path.write_bytes(_PLACEHOLDER_PNG)
        self.calls.append(("take_screenshot", session_id))
        return str(out_path)

    def run_integration_test(
        self, project_path: str, test_file: str, device_id: str, timeout_seconds: float
    ) -> TestRunResult:
        self._find_device(device_id)
        self.calls.append(("run_integration_test", project_path, test_file, device_id))
        passed = "fail" not in test_file.lower()
        command = f"flutter test integration_test/{test_file} -d {device_id}"
        if passed:
            stdout, stderr = "00:01 +1: All tests passed!", ""
        else:
            stdout, stderr = "00:01 +0 -1: some tests failed.", f"Test failed: {test_file}"
        return TestRunResult(
            command=command,
            exit_code=0 if passed else 1,
            passed=passed,
            stdout=stdout,
            stderr=stderr,
        )
