import os

from dev_environment.processes import list_processes


def test_list_processes_returns_at_least_the_current_process():
    procs = list_processes()

    assert any(p.pid == os.getpid() for p in procs)


def test_list_processes_filters_by_name_substring():
    all_procs = list_processes()
    assert all_procs, "expected at least one running process to test against"
    target_name = all_procs[0].name

    filtered = list_processes(target_name[: max(1, len(target_name) // 2)])

    assert any(p.name == target_name for p in filtered)


def test_list_processes_filter_with_no_matches_returns_empty():
    procs = list_processes("this-process-name-will-never-exist-xyz")
    assert procs == []
