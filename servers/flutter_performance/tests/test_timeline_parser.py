import pytest

from flutter_performance.timeline_parser import load_trace_events


def test_load_trace_events_accepts_bare_array():
    events = [{"name": "Frame", "ph": "X", "ts": 0, "dur": 100}]

    assert load_trace_events(events) == events


def test_load_trace_events_accepts_trace_events_object():
    events = [{"name": "Frame", "ph": "X", "ts": 0, "dur": 100}]
    data = {"traceEvents": events, "displayTimeUnit": "ms"}

    assert load_trace_events(data) == events


def test_load_trace_events_rejects_unrecognized_shape():
    with pytest.raises(ValueError, match="Not a recognizable"):
        load_trace_events({"unexpected": "shape"})


def test_load_trace_events_rejects_non_list_trace_events():
    with pytest.raises(ValueError, match="Not a recognizable"):
        load_trace_events({"traceEvents": "not-a-list"})
