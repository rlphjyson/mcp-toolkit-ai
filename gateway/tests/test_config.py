import sys

import pytest

from mcp_gateway.config import find_config_file, load_servers, to_stdio_params

TOML_CONTENT = """
[servers.alpha]
description = "First test server"
command = "python"
args = ["-m", "alpha.server"]
cwd = "servers/alpha"

[servers.beta]
description = "Second test server"
command = "some-other-binary"
args = []
cwd = "servers/beta"

[servers.gamma]
description = "Third test server, with env vars"
command = "python"
args = []
cwd = "servers/alpha"
env = { TOKEN = "${MCP_GATEWAY_TEST_TOKEN}", LITERAL = "no-substitution-here" }

[servers.gateway]
description = "The gateway's own entry -- must never be treated as a backend"
command = "python"
args = ["-m", "mcp_gateway.server"]
cwd = "gateway"
"""


@pytest.fixture(name="config_path")
def config_path_fixture(tmp_path):
    (tmp_path / "servers" / "alpha").mkdir(parents=True)
    (tmp_path / "servers" / "beta").mkdir(parents=True)
    config_file = tmp_path / "servers.toml"
    config_file.write_text(TOML_CONTENT)
    return config_file


def test_load_servers_parses_all_entries_except_the_gateways_own(config_path):
    servers = load_servers(config_path)

    assert set(servers) == {"alpha", "beta", "gamma"}
    assert servers["alpha"].description == "First test server"
    assert servers["alpha"].args == ["-m", "alpha.server"]


def test_load_servers_resolves_cwd_relative_to_config_file(config_path):
    servers = load_servers(config_path)

    assert servers["alpha"].cwd == (config_path.parent / "servers" / "alpha").resolve()


def test_find_config_file_walks_up_from_a_nested_directory(config_path):
    repo_root = config_path.parent
    nested = repo_root / "servers" / "alpha"

    found = find_config_file(nested)

    assert found == config_path


def test_find_config_file_raises_when_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        find_config_file(tmp_path)


def test_to_stdio_params_substitutes_current_interpreter_for_python(config_path):
    servers = load_servers(config_path)

    params = to_stdio_params(servers["alpha"])

    assert params.command == sys.executable
    assert params.args == ["-m", "alpha.server"]


def test_to_stdio_params_leaves_non_python_commands_untouched(config_path):
    servers = load_servers(config_path)

    params = to_stdio_params(servers["beta"])

    assert params.command == "some-other-binary"


def test_env_vars_are_expanded_from_the_gateways_process_environment(config_path, monkeypatch):
    monkeypatch.setenv("MCP_GATEWAY_TEST_TOKEN", "secret-value")

    servers = load_servers(config_path)

    assert servers["gamma"].env == {"TOKEN": "secret-value", "LITERAL": "no-substitution-here"}


def test_missing_env_var_expands_to_empty_string(config_path, monkeypatch):
    monkeypatch.delenv("MCP_GATEWAY_TEST_TOKEN", raising=False)

    servers = load_servers(config_path)

    assert servers["gamma"].env["TOKEN"] == ""
