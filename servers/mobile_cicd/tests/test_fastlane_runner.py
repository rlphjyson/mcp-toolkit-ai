import pytest

from mobile_cicd.fastlane_runner import (
    FastlaneTimeoutError,
    list_available_lanes,
    run_fastlane_lane,
)

FASTFILE_CONTENTS = """\
default_platform(:ios)

platform :ios do
  lane :beta do
    build_app(scheme: "Runner")
    upload_to_testflight
  end

  lane :release do
    build_app(scheme: "Runner")
    upload_to_app_store
  end
end
"""


def test_list_available_lanes_finds_ios_lanes(tmp_path):
    fastfile_dir = tmp_path / "ios" / "fastlane"
    fastfile_dir.mkdir(parents=True)
    (fastfile_dir / "Fastfile").write_text(FASTFILE_CONTENTS)

    lanes = list_available_lanes(tmp_path)

    assert lanes == ["beta", "release"]


def test_list_available_lanes_finds_android_lanes(tmp_path):
    fastfile_dir = tmp_path / "android" / "fastlane"
    fastfile_dir.mkdir(parents=True)
    (fastfile_dir / "Fastfile").write_text("lane :internal do\nend\n")

    lanes = list_available_lanes(tmp_path)

    assert lanes == ["internal"]


def test_list_available_lanes_combines_both_platforms(tmp_path):
    ios_dir = tmp_path / "ios" / "fastlane"
    ios_dir.mkdir(parents=True)
    (ios_dir / "Fastfile").write_text("lane :beta do\nend\n")
    android_dir = tmp_path / "android" / "fastlane"
    android_dir.mkdir(parents=True)
    (android_dir / "Fastfile").write_text("lane :internal do\nend\n")

    lanes = list_available_lanes(tmp_path)

    assert lanes == ["beta", "internal"]


def test_list_available_lanes_returns_empty_list_when_no_fastfile(tmp_path):
    lanes = list_available_lanes(tmp_path)

    assert lanes == []


def test_run_fastlane_lane_raises_value_error_when_fastlane_not_installed(tmp_path):
    # Uses the `command` seam to force a FileNotFoundError deterministically -- relying on the
    # real `fastlane` binary being absent from PATH isn't portable: GitHub's hosted ubuntu-latest
    # runner ships fastlane preinstalled as standard mobile-CI tooling, so the plain default
    # `["fastlane", lane]` command doesn't reliably fail there the way it does in a bare sandbox.
    with pytest.raises(ValueError, match="fastlane is not installed"):
        run_fastlane_lane(
            tmp_path,
            "beta",
            timeout_seconds=10,
            command=["definitely-not-a-real-fastlane-binary-xyz", "beta"],
        )


def test_run_fastlane_lane_raises_fastlane_timeout_error(tmp_path):
    with pytest.raises(FastlaneTimeoutError, match="beta.*timed out"):
        run_fastlane_lane(
            tmp_path, "beta", timeout_seconds=0.1, command=["sleep", "5"]
        )


def test_run_fastlane_lane_reports_success(tmp_path):
    import sys

    result = run_fastlane_lane(
        tmp_path,
        "beta",
        timeout_seconds=10,
        command=[sys.executable, "-c", "print('ok')"],
    )

    assert result.passed is True
    assert result.exit_code == 0
    assert "ok" in result.stdout
    assert result.lane == "beta"


def test_run_fastlane_lane_reports_failure(tmp_path):
    import sys

    result = run_fastlane_lane(
        tmp_path,
        "beta",
        timeout_seconds=10,
        command=[sys.executable, "-c", "import sys; sys.exit(1)"],
    )

    assert result.passed is False
    assert result.exit_code == 1
