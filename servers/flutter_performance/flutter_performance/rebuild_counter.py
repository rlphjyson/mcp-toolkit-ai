"""Best-effort widget-rebuild counting from a Flutter DevTools timeline export.

Flutter does not guarantee a stable, version-independent timeline event name for an individual
widget's build method: depending on the Flutter/engine version and the timeline event flags in
use, build work may show up as an event literally named "<Widget>.build", as a generic "BUILD" or
"Widget.build"-style marker, or under some other build-related name. This module treats any event
whose name contains "build" (case-insensitively) as a rebuild marker, and where the name matches
"<Identifier>.build" normalizes it to just the identifier so per-widget counts group correctly.
This is a heuristic, not an exact instrumentation of Flutter's build system, and results should be
read as an approximation.
"""

import re
from dataclasses import dataclass

_BUILD_SUFFIX = re.compile(r"(\w+)\.build$")


def _normalize_name(name: str) -> str:
    match = _BUILD_SUFFIX.search(name)
    return match.group(1) if match else name


def _is_build_event(name: str) -> bool:
    return bool(_BUILD_SUFFIX.search(name)) or "build" in name.lower()


@dataclass
class _RebuildStats:
    count: int = 0
    total_duration_us: float = 0.0


def count_widget_rebuilds(events: list[dict]) -> list[dict]:
    """Groups build-marker events by (heuristically normalized) name and counts occurrences.

    See module docstring for the heuristic and its limits. Returns entries sorted by
    rebuild_count descending.
    """
    stats: dict[str, _RebuildStats] = {}
    begin_stacks: dict[tuple[str, object, object], list[float]] = {}

    def record(name: str, duration_us: float) -> None:
        entry = stats.setdefault(_normalize_name(name), _RebuildStats())
        entry.count += 1
        entry.total_duration_us += duration_us

    for event in events:
        name = event.get("name") or ""
        if not _is_build_event(name):
            continue
        phase = event.get("ph")

        if phase == "X":
            record(name, float(event.get("dur") or 0.0))
        elif phase == "B":
            key = (name, event.get("pid"), event.get("tid"))
            ts = event.get("ts")
            if ts is not None:
                begin_stacks.setdefault(key, []).append(float(ts))
        elif phase == "E":
            key = (name, event.get("pid"), event.get("tid"))
            stack = begin_stacks.get(key)
            ts = event.get("ts")
            if stack and ts is not None:
                start_ts = stack.pop()
                record(name, float(ts) - start_ts)

    results: list[dict] = [
        {
            "name": name,
            "rebuild_count": entry.count,
            "total_duration_ms": entry.total_duration_us / 1000,
        }
        for name, entry in stats.items()
    ]
    results.sort(key=lambda r: int(r["rebuild_count"]), reverse=True)
    return results
