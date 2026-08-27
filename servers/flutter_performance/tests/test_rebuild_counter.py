from flutter_performance.rebuild_counter import count_widget_rebuilds

EVENTS = [
    {"name": "MyWidget.build", "ph": "X", "ts": 0, "dur": 1_000, "pid": 1, "tid": 1},
    {"name": "MyWidget.build", "ph": "X", "ts": 1_000, "dur": 2_000, "pid": 1, "tid": 1},
    {"name": "OtherWidget.build", "ph": "X", "ts": 2_000, "dur": 500, "pid": 1, "tid": 1},
    {"name": "BUILD", "ph": "X", "ts": 3_000, "dur": 100, "pid": 1, "tid": 1},
    {"name": "Unrelated", "ph": "X", "ts": 4_000, "dur": 999, "pid": 1, "tid": 1},
]


def test_count_widget_rebuilds_groups_by_normalized_name():
    results = count_widget_rebuilds(EVENTS)

    by_name = {r["name"]: r for r in results}
    assert by_name["MyWidget"]["rebuild_count"] == 2
    assert by_name["MyWidget"]["total_duration_ms"] == 3.0
    assert by_name["OtherWidget"]["rebuild_count"] == 1
    assert by_name["BUILD"]["rebuild_count"] == 1


def test_count_widget_rebuilds_ignores_non_build_events():
    results = count_widget_rebuilds(EVENTS)

    assert "Unrelated" not in {r["name"] for r in results}


def test_count_widget_rebuilds_sorted_by_count_descending():
    results = count_widget_rebuilds(EVENTS)

    counts = [r["rebuild_count"] for r in results]
    assert counts == sorted(counts, reverse=True)


def test_count_widget_rebuilds_pairs_begin_end_events():
    events = [
        {"name": "Card.build", "ph": "B", "ts": 0, "pid": 1, "tid": 1},
        {"name": "Card.build", "ph": "E", "ts": 4_000, "pid": 1, "tid": 1},
    ]

    results = count_widget_rebuilds(events)

    assert results == [{"name": "Card", "rebuild_count": 1, "total_duration_ms": 4.0}]


def test_count_widget_rebuilds_empty_when_no_build_events():
    assert count_widget_rebuilds([{"name": "Unrelated", "ph": "X", "dur": 1}]) == []
