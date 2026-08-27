"""Analysis of `flutter build --analyze-size` code-size-analysis JSON reports.

The report is a recursive tree of {"n": name, "children": [...], "value": bytes} nodes. A node
with no children is a leaf contributing its own "value"; a node with children is an internal
grouping node whose size is the sum of its descendants' leaf values.
"""


def flatten_size_tree(node: dict, path: str = "") -> list[dict]:
    """Recursively walks a size tree, returning leaf entries as {"path", "name", "size_bytes"}.

    "path" is the "/"-joined chain of ancestor names down to (and including) the leaf.
    """
    name = node.get("n", "")
    current_path = f"{path}/{name}" if path else name
    children = node.get("children") or []

    if children:
        entries = []
        for child in children:
            entries.extend(flatten_size_tree(child, current_path))
        return entries

    return [{"path": current_path, "name": name, "size_bytes": node.get("value", 0)}]


def analyze_app_size(tree: dict, top_n: int = 20) -> dict:
    """Summarizes total size and the largest individual contributors in a size tree."""
    leaves = flatten_size_tree(tree)
    total_size_bytes = sum(leaf["size_bytes"] for leaf in leaves)
    largest_contributors = sorted(leaves, key=lambda leaf: leaf["size_bytes"], reverse=True)[
        :top_n
    ]
    return {"total_size_bytes": total_size_bytes, "largest_contributors": largest_contributors}
