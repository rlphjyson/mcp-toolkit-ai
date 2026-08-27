"""Frame-jank analysis over Chrome Trace Event Format data exported from Flutter DevTools.

Flutter/engine timeline event names for per-frame build+raster work vary across Flutter and
engine versions and timeline configurations (e.g. "Frame", "GPURasterizer::Draw", VSYNC-related
markers), so this module takes a best-effort approach: any event whose name contains "frame"
(case-insensitive) is treated as frame work, whether it arrives as a single complete ("X" phase)
event carrying a "dur" field, or as a matched Begin/End ("B"/"E") pair sharing the same name,
pid, and tid.
"""

from dataclasses import dataclass

from flutter_performance.config import DEFAULT_JANK_THRESHOLD_MS


@dataclass
class FrameSpan:
    start_ts_us: float
    duration_us: float


def _extract_frame_spans(events: list[dict]) -> list[FrameSpan]:
    spans: list[FrameSpan] = []
    begin_stacks: dict[tuple[str, object, object], list[float]] = {}

    for event in events:
        name = event.get("name") or ""
        if "frame" not in name.lower():
            continue
        phase = event.get("ph")

        if phase == "X":
            dur = event.get("dur")
            ts = event.get("ts")
            if dur is not None and ts is not None:
                spans.append(FrameSpan(start_ts_us=float(ts), duration_us=float(dur)))
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
                spans.append(FrameSpan(start_ts_us=start_ts, duration_us=float(ts) - start_ts))

    return spans


def extract_frame_durations_us(events: list[dict]) -> list[float]:
    """Returns the duration (microseconds) of every detected frame span."""
    return [span.duration_us for span in _extract_frame_spans(events)]


def find_jank_frames(
    events: list[dict], threshold_ms: float = DEFAULT_JANK_THRESHOLD_MS
) -> list[dict]:
    """Returns frames whose duration exceeds threshold_ms, worst (slowest) first."""
    threshold_us = threshold_ms * 1000
    jank = [span for span in _extract_frame_spans(events) if span.duration_us > threshold_us]
    jank.sort(key=lambda span: span.duration_us, reverse=True)
    return [
        {"start_ts_us": span.start_ts_us, "duration_ms": span.duration_us / 1000} for span in jank
    ]


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    index = min(len(sorted_values) - 1, round(pct / 100 * (len(sorted_values) - 1)))
    return sorted_values[index]


def summarize_frame_times(events: list[dict]) -> dict:
    """Summarizes frame build+raster durations detected in the timeline."""
    durations_ms = sorted(us / 1000 for us in extract_frame_durations_us(events))
    frame_count = len(durations_ms)

    if frame_count == 0:
        return {
            "frame_count": 0,
            "avg_ms": 0.0,
            "p50_ms": 0.0,
            "p95_ms": 0.0,
            "p99_ms": 0.0,
            "jank_count": 0,
            "jank_percent": 0.0,
        }

    jank_count = sum(1 for d in durations_ms if d > DEFAULT_JANK_THRESHOLD_MS)

    return {
        "frame_count": frame_count,
        "avg_ms": sum(durations_ms) / frame_count,
        "p50_ms": _percentile(durations_ms, 50),
        "p95_ms": _percentile(durations_ms, 95),
        "p99_ms": _percentile(durations_ms, 99),
        "jank_count": jank_count,
        "jank_percent": jank_count / frame_count * 100,
    }
