import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

_LANE_PATTERN = re.compile(r"lane\s+:(\w+)\s+do")


class FastlaneTimeoutError(RuntimeError):
    pass


@dataclass
class FastlaneResult:
    lane: str
    exit_code: int
    passed: bool
    stdout: str
    stderr: str


def run_fastlane_lane(
    project_path: Path,
    lane: str,
    timeout_seconds: float,
    command: list[str] | None = None,
) -> FastlaneResult:
    # command is a testing seam (not an MCP tool parameter) letting tests exercise the
    # timeout-translation path with a trivial real subprocess instead of a real fastlane install.
    args = command if command is not None else ["fastlane", lane]

    try:
        process = subprocess.run(
            args,
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise FastlaneTimeoutError(
            f"Fastlane lane '{lane}' timed out after {timeout_seconds}s"
        ) from exc
    except FileNotFoundError as exc:
        raise ValueError(
            "fastlane is not installed or not on PATH. Install it (e.g. `brew install fastlane` "
            "or `gem install fastlane`) and ensure it's reachable from this server's environment."
        ) from exc

    return FastlaneResult(
        lane=lane,
        exit_code=process.returncode,
        passed=process.returncode == 0,
        stdout=process.stdout,
        stderr=process.stderr,
    )


def list_available_lanes(project_path: Path) -> list[str]:
    lanes: list[str] = []
    for platform in ("ios", "android"):
        fastfile = project_path / platform / "fastlane" / "Fastfile"
        if fastfile.is_file():
            lanes.extend(_LANE_PATTERN.findall(fastfile.read_text()))
    return lanes
