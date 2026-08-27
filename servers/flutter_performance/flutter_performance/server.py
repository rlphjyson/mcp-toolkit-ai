import json
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import TypeVar

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from flutter_performance.config import DEFAULT_JANK_THRESHOLD_MS, DEFAULT_SIZE_TOP_N
from flutter_performance.jank_analysis import find_jank_frames as _find_jank_frames
from flutter_performance.jank_analysis import summarize_frame_times
from flutter_performance.rebuild_counter import count_widget_rebuilds as _count_widget_rebuilds
from flutter_performance.size_analysis import analyze_app_size as _analyze_app_size
from flutter_performance.timeline_parser import load_trace_events

server = MCPServer(
    "flutter-performance",
    instructions=(
        "Analyzes Flutter DevTools timeline exports (Chrome Trace Event Format JSON) for jank "
        "and slow frames, and `flutter build --analyze-size` code-size-analysis JSON reports "
        "for app-size bloat. Pure offline analysis of files the caller has already captured -- "
        "no live device or profiling session is involved."
    ),
)

T = TypeVar("T")

# See dev_environment/server.py: MCPServer redacts a plain exception's message from the caller by
# default and only preserves a deliberately-raised ToolError's -- this surfaces safe, specific
# validation/parsing error text instead of a generic one.
KNOWN_SAFE_ERRORS = (ValueError, FileNotFoundError)


def surface_known_errors(fn: Callable[..., T]) -> Callable[..., T]:
    @wraps(fn)
    def wrapper(*args: object, **kwargs: object) -> T:
        try:
            return fn(*args, **kwargs)
        except KNOWN_SAFE_ERRORS as exc:
            raise ToolError(str(exc)) from exc

    return wrapper


def _load_timeline_events(path: str) -> list[dict]:
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"No such timeline file: {path}")
    with file_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return load_trace_events(data)


def _load_size_tree(path: str) -> dict:
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"No such size analysis file: {path}")
    with file_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(
            f"Not a recognizable app-size analysis tree (expected a JSON object): {path}"
        )
    return data


@server.tool()
@surface_known_errors
def analyze_timeline(timeline_json_path: str) -> dict:
    """Loads a DevTools timeline export and summarizes frame build+raster times: frame count,
    average/p50/p95/p99 durations, jank count/percent, and a sample of the worst frames."""
    events = _load_timeline_events(timeline_json_path)
    summary = summarize_frame_times(events)
    worst_frames = _find_jank_frames(events, DEFAULT_JANK_THRESHOLD_MS)
    summary["jank_frame_count"] = len(worst_frames)
    summary["worst_frames"] = worst_frames[:5]
    return summary


@server.tool()
@surface_known_errors
def find_jank_frames(timeline_json_path: str, threshold_ms: float = DEFAULT_JANK_THRESHOLD_MS) -> list[dict]:
    """Loads a DevTools timeline export and returns frames whose duration exceeds threshold_ms,
    worst (slowest) first, as [{"start_ts_us", "duration_ms"}]."""
    events = _load_timeline_events(timeline_json_path)
    return _find_jank_frames(events, threshold_ms)


@server.tool()
@surface_known_errors
def count_widget_rebuilds(timeline_json_path: str) -> list[dict]:
    """Loads a DevTools timeline export and best-effort counts widget rebuilds by matching
    build-marker event names, returning [{"name", "rebuild_count", "total_duration_ms"}] sorted
    by rebuild_count descending. Heuristic: Flutter does not guarantee a stable per-widget build
    event name across versions or timeline configurations."""
    events = _load_timeline_events(timeline_json_path)
    return _count_widget_rebuilds(events)


@server.tool()
@surface_known_errors
def analyze_app_size(size_json_path: str, top_n: int = DEFAULT_SIZE_TOP_N) -> dict:
    """Loads a `flutter build --analyze-size` code-size-analysis JSON report and returns total
    size plus the top_n largest individual contributors."""
    tree = _load_size_tree(size_json_path)
    return _analyze_app_size(tree, top_n)


if __name__ == "__main__":
    server.run()
