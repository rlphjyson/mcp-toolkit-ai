from codebase_intelligence.repo_registry import RepoRegistry, repo_id_for


def test_repo_id_is_deterministic_for_the_same_path(tmp_path):
    assert repo_id_for(tmp_path) == repo_id_for(tmp_path)


def test_repo_id_differs_for_different_paths(tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    assert repo_id_for(tmp_path) != repo_id_for(other)


def test_register_then_resolve_roundtrip(tmp_path):
    registry_path = tmp_path / "registry.json"
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    registry = RepoRegistry(registry_path)

    repo_id = registry.register(repo_dir)

    assert registry.resolve(repo_id) == repo_dir.resolve()


def test_resolve_returns_none_for_unknown_id(tmp_path):
    registry = RepoRegistry(tmp_path / "registry.json")
    assert registry.resolve("does-not-exist") is None


def test_registry_persists_across_instances(tmp_path):
    registry_path = tmp_path / "registry.json"
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    repo_id = RepoRegistry(registry_path).register(repo_dir)
    reloaded = RepoRegistry(registry_path)

    assert reloaded.resolve(repo_id) == repo_dir.resolve()


def test_registering_the_same_path_twice_reuses_the_id(tmp_path):
    registry = RepoRegistry(tmp_path / "registry.json")
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    first = registry.register(repo_dir)
    second = registry.register(repo_dir)

    assert first == second
