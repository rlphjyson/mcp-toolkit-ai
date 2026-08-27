import pytest

from flutter_project_intelligence.project_index import ProjectIndex
from flutter_project_intelligence.project_registry import ProjectRegistry, project_id_for


def _index(root):
    return ProjectIndex(
        project_id=project_id_for(root),
        root=root.resolve(),
        package_name="my_app",
        flutter_sdk_constraint=None,
        dependencies={},
        dev_dependencies={},
    )


def test_project_id_for_is_deterministic_for_the_same_path(tmp_path):
    assert project_id_for(tmp_path) == project_id_for(tmp_path)


def test_project_id_for_differs_for_different_paths(tmp_path):
    other = tmp_path / "other"
    other.mkdir()

    assert project_id_for(tmp_path) != project_id_for(other)


def test_put_then_get_roundtrip(tmp_path):
    registry = ProjectRegistry()
    index = _index(tmp_path)

    registry.put(index)

    assert registry.get(index.project_id) is index


def test_get_raises_for_unknown_project_id():
    registry = ProjectRegistry()

    with pytest.raises(ValueError, match="Unknown project_id"):
        registry.get("does-not-exist")


def test_put_the_same_path_twice_reuses_the_project_id(tmp_path):
    registry = ProjectRegistry()
    first = _index(tmp_path)
    second = _index(tmp_path)

    registry.put(first)
    registry.put(second)

    assert first.project_id == second.project_id
    assert registry.get(first.project_id) is second
