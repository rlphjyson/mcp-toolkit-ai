import sys

import pytest

from dev_environment.test_runner import RunTimeoutError, run_tests


def test_run_tests_reports_success(tmp_path):
    result = run_tests(tmp_path, f"{sys.executable} -c \"print('ok')\"", timeout_seconds=10)

    assert result.passed is True
    assert result.exit_code == 0
    assert "ok" in result.stdout


def test_run_tests_reports_failure(tmp_path):
    result = run_tests(tmp_path, f"{sys.executable} -c \"import sys; sys.exit(1)\"", timeout_seconds=10)

    assert result.passed is False
    assert result.exit_code == 1


def test_run_tests_raises_on_empty_command(tmp_path):
    with pytest.raises(ValueError, match="No command"):
        run_tests(tmp_path, "", timeout_seconds=10)


def test_run_tests_raises_on_unknown_command(tmp_path):
    with pytest.raises(ValueError, match="Command not found"):
        run_tests(tmp_path, "this-command-does-not-exist-anywhere", timeout_seconds=10)


def test_run_tests_times_out_on_a_slow_command(tmp_path):
    with pytest.raises(RunTimeoutError, match="timed out"):
        run_tests(tmp_path, f"{sys.executable} -c \"import time; time.sleep(5)\"", timeout_seconds=0.5)
