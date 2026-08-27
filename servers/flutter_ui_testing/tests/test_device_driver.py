import json
from pathlib import Path

import pytest

from flutter_ui_testing.device_driver import (
    Device,
    DeviceNotFoundError,
    FakeDeviceDriver,
    parse_devices_json,
)


def test_parse_devices_json_maps_android_target():
    raw = json.dumps(
        [{"id": "emulator-5554", "name": "Pixel", "targetPlatform": "android-arm64", "emulator": True}]
    )

    devices = parse_devices_json(raw)

    assert devices == [Device(id="emulator-5554", name="Pixel", platform="android", is_emulator=True)]


def test_parse_devices_json_maps_ios_target():
    raw = json.dumps([{"id": "ABCD", "name": "iPhone 14", "targetPlatform": "ios", "emulator": True}])

    devices = parse_devices_json(raw)

    assert devices[0].platform == "ios"
    assert devices[0].is_emulator is True


def test_parse_devices_json_maps_unknown_target_to_web():
    raw = json.dumps(
        [{"id": "chrome", "name": "Chrome", "targetPlatform": "web-javascript", "emulator": False}]
    )

    devices = parse_devices_json(raw)

    assert devices[0].platform == "web"
    assert devices[0].is_emulator is False


def test_parse_devices_json_rejects_malformed_json():
    with pytest.raises(ValueError, match="Could not parse"):
        parse_devices_json("not json")


def test_fake_driver_lists_one_android_and_one_ios_device():
    driver = FakeDeviceDriver()

    devices = driver.list_devices()

    platforms = {d.platform for d in devices}
    assert platforms == {"android", "ios"}


def test_fake_driver_launch_then_interact_records_call_log():
    driver = FakeDeviceDriver()
    session = driver.launch_app("/repo", "emulator-5554")

    driver.tap(session.session_id, 10, 20)
    driver.enter_text(session.session_id, "hello")
    driver.scroll(session.session_id, 0, -100)

    assert driver.calls == [
        ("launch_app", "/repo", "emulator-5554"),
        ("tap", session.session_id, 10, 20),
        ("enter_text", session.session_id, "hello"),
        ("scroll", session.session_id, 0, -100),
    ]


def test_fake_driver_launch_app_rejects_unknown_device():
    driver = FakeDeviceDriver()

    with pytest.raises(DeviceNotFoundError, match="Unknown device id"):
        driver.launch_app("/repo", "no-such-device")


def test_fake_driver_tap_rejects_unknown_session():
    driver = FakeDeviceDriver()

    with pytest.raises(DeviceNotFoundError, match="Unknown session id"):
        driver.tap("no-such-session", 0, 0)


def test_fake_driver_stop_app_removes_session():
    driver = FakeDeviceDriver()
    session = driver.launch_app("/repo", "emulator-5554")

    driver.stop_app(session.session_id)

    with pytest.raises(DeviceNotFoundError):
        driver.tap(session.session_id, 0, 0)


def test_fake_driver_take_screenshot_writes_a_real_png_file(tmp_path, monkeypatch):
    monkeypatch.setattr("flutter_ui_testing.device_driver.SCREENSHOT_DIR", str(tmp_path))
    driver = FakeDeviceDriver()
    session = driver.launch_app("/repo", "emulator-5554")

    path = driver.take_screenshot(session.session_id)

    data = Path(path).read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"


def test_fake_driver_run_integration_test_passes_by_default():
    driver = FakeDeviceDriver()

    result = driver.run_integration_test("/repo", "app_test.dart", "emulator-5554", 30)

    assert result.passed is True
    assert result.exit_code == 0


def test_fake_driver_run_integration_test_fails_when_file_name_contains_fail():
    driver = FakeDeviceDriver()

    result = driver.run_integration_test("/repo", "login_fail_test.dart", "emulator-5554", 30)

    assert result.passed is False
    assert result.exit_code == 1
