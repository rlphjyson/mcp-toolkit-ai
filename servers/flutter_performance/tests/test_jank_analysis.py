from flutter_performance.jank_analysis import (
    extract_frame_durations_us,
    find_jank_frames,
    summarize_frame_times,
)

COMPLETE_EVENTS = [
    {"name": "Frame", "ph": "X", "ts": 1_000, "dur": 10_000, "pid": 1, "tid": 1},  # 10ms
    {"name": "Frame", "ph": "X", "ts": 2_000, "dur": 25_000, "pid": 1, "tid": 1},  # 25ms, jank
    {"name": "SomethingElse", "ph": "X", "ts": 3_000, "dur": 5_000, "pid": 1, "tid": 1},
]

PAIRED_EVENTS = [
    {"name": "Frame", "ph": "B", "ts": 5_000, "pid": 1, "tid": 2},
    {"name": "Frame", "ph": "E", "ts": 25_000, "pid": 1, "tid": 2},  # 20ms, jank
    {"name": "Frame", "ph": "B", "ts": 30_000, "pid": 1, "tid": 2},
    {"name": "Frame", "ph": "E", "ts": 35_000, "pid": 1, "tid": 2},  # 5ms
]


def test_extract_frame_durations_us_reads_complete_events():
    durations = extract_frame_durations_us(COMPLETE_EVENTS)

    assert sorted(durations) == [10_000.0, 25_000.0]


def test_extract_frame_durations_us_reconstructs_from_begin_end_pairs():
    durations = extract_frame_durations_us(PAIRED_EVENTS)

    assert sorted(durations) == [5_000.0, 20_000.0]


def test_find_jank_frames_filters_and_sorts_worst_first():
    jank = find_jank_frames(COMPLETE_EVENTS + PAIRED_EVENTS, threshold_ms=16.67)

    assert [f["duration_ms"] for f in jank] == [25.0, 20.0]
    assert jank[0]["start_ts_us"] == 2_000


def test_find_jank_frames_empty_when_nothing_exceeds_threshold():
    jank = find_jank_frames(COMPLETE_EVENTS, threshold_ms=1000)

    assert jank == []


def test_summarize_frame_times_computes_stats():
    summary = summarize_frame_times(COMPLETE_EVENTS)

    assert summary["frame_count"] == 2
    assert summary["jank_count"] == 1
    assert summary["jank_percent"] == 50.0
    assert summary["avg_ms"] == 17.5


def test_summarize_frame_times_handles_no_frames():
    summary = summarize_frame_times([{"name": "Unrelated", "ph": "X", "ts": 0, "dur": 100}])

    assert summary["frame_count"] == 0
    assert summary["jank_percent"] == 0.0
