from flutter_performance.size_analysis import analyze_app_size, flatten_size_tree

TREE = {
    "n": "root",
    "children": [
        {"n": "a", "value": 100},
        {
            "n": "b",
            "children": [
                {"n": "b1", "value": 50},
                {"n": "b2", "value": 150},
            ],
        },
    ],
}


def test_flatten_size_tree_returns_only_leaves():
    leaves = flatten_size_tree(TREE)

    assert leaves == [
        {"path": "root/a", "name": "a", "size_bytes": 100},
        {"path": "root/b/b1", "name": "b1", "size_bytes": 50},
        {"path": "root/b/b2", "name": "b2", "size_bytes": 150},
    ]


def test_flatten_size_tree_handles_a_single_leaf_root():
    assert flatten_size_tree({"n": "solo", "value": 42}) == [
        {"path": "solo", "name": "solo", "size_bytes": 42}
    ]


def test_analyze_app_size_totals_and_ranks_contributors():
    result = analyze_app_size(TREE, top_n=2)

    assert result["total_size_bytes"] == 300
    assert result["largest_contributors"] == [
        {"path": "root/b/b2", "name": "b2", "size_bytes": 150},
        {"path": "root/a", "name": "a", "size_bytes": 100},
    ]


def test_analyze_app_size_top_n_caps_results():
    result = analyze_app_size(TREE, top_n=1)

    assert len(result["largest_contributors"]) == 1
