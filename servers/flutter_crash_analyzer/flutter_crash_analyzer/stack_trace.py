import re
from dataclasses import dataclass

FRAME_RE = re.compile(r"^#(?P<index>\d+)\s+(?P<function>.+?)\s+\((?P<location>[^()]+)\)\s*$")
THROWN_RE = re.compile(r"The following (?P<type>.+?) was thrown")
UNHANDLED_RE = re.compile(r"^Unhandled exception:\s*$", re.MULTILINE)


@dataclass
class StackFrame:
    index: int
    function: str
    file: str | None
    line: int | None
    column: int | None
    is_project_code: bool


@dataclass
class ParsedException:
    exception_type: str
    message: str
    frames: list[StackFrame]


def parse_stack_trace(text: str, project_package_name: str | None = None) -> ParsedException:
    if not text or not text.strip():
        raise ValueError("trace_text is empty")

    frames = _parse_frames(text, project_package_name)
    exception_type, message = _parse_header(text)

    if exception_type is None and not frames:
        raise ValueError("Could not find a recognized exception header or stack frame in trace_text")

    return ParsedException(
        exception_type=exception_type or "UnknownException", message=message, frames=frames
    )


def _parse_frames(text: str, project_package_name: str | None) -> list[StackFrame]:
    frames = []
    for raw_line in text.splitlines():
        match = FRAME_RE.match(raw_line.strip())
        if not match:
            continue
        file, line, column = _split_location(match.group("location").strip())
        frames.append(
            StackFrame(
                index=int(match.group("index")),
                function=match.group("function").strip(),
                file=file,
                line=line,
                column=column,
                is_project_code=_is_project_code(file, project_package_name),
            )
        )
    return frames


def _split_location(location: str) -> tuple[str | None, int | None, int | None]:
    if not location:
        return None, None, None

    parts = location.rsplit(":", 2)
    if len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
        return parts[0], int(parts[1]), int(parts[2])

    parts = location.rsplit(":", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return parts[0], int(parts[1]), None

    return location, None, None


def to_repo_relative_path(file: str, project_package_name: str | None) -> str:
    """Maps a `package:<name>/...` URI onto the conventional `lib/...` path pub packages use on
    disk, so it can be handed to `git blame`. Non-package paths (already relative) pass through."""
    if project_package_name:
        prefix = f"package:{project_package_name}/"
        if file.startswith(prefix):
            return "lib/" + file[len(prefix) :]
    return file


def _is_project_code(file: str | None, project_package_name: str | None) -> bool:
    if not file:
        return False
    if file.startswith("dart:"):
        return False
    if file.startswith("package:"):
        return bool(project_package_name) and file.startswith(f"package:{project_package_name}/")
    return True


def _parse_header(text: str) -> tuple[str | None, str]:
    match = THROWN_RE.search(text)
    if match:
        return match.group("type").strip(), _message_after(text, match.end())

    match = UNHANDLED_RE.search(text)
    if match:
        rest = text[match.end() :].lstrip("\n")
        first_line = rest.split("\n", 1)[0].strip()
        if ":" in first_line:
            exception_type, _, message = first_line.partition(":")
            return exception_type.strip(), message.strip()
        return first_line or None, ""

    return None, ""


def _message_after(text: str, start: int) -> str:
    lines = text[start:].split("\n")
    message_lines = []
    for line in lines[1:]:
        stripped = line.strip()
        if not stripped or stripped.startswith("When the exception was thrown"):
            break
        message_lines.append(stripped)
    return " ".join(message_lines)
