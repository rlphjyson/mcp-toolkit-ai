import os
import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from mcp.client.stdio import StdioServerParameters

# Deliberately duplicated from cli/mcp_toolkit/config.py rather than shared -- this package is
# independently installable, same as every server, and the config-loading logic is small enough
# that a path/editable cross-package dependency isn't worth the coupling.

CONFIG_FILENAME = "servers.toml"
ENV_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

# The gateway's own entry in servers.toml (added so it's reachable through the CLI too) must
# never be treated as a backend to connect to -- that would make the gateway spawn itself.
GATEWAY_OWN_SHORT_NAME = "gateway"


@dataclass
class ServerConfig:
    name: str
    description: str
    command: str
    args: list[str]
    cwd: Path
    env: dict[str, str] = field(default_factory=dict)


def find_config_file(start: Path) -> Path:
    """Walks upward from `start` looking for servers.toml, the way git/pytest find their own
    config -- lets the gateway be launched from any directory inside the repo, not just the
    root."""
    current = start.resolve()
    for candidate in (current, *current.parents):
        config_path = candidate / CONFIG_FILENAME
        if config_path.is_file():
            return config_path
    raise FileNotFoundError(
        f"Could not find {CONFIG_FILENAME} in {start} or any parent directory."
    )


def _expand_env_vars(value: str) -> str:
    """Expands ${VAR_NAME} references against the gateway's own environment, so servers.toml can
    reference e.g. a GitHub token without the secret itself living in the file."""

    def replace(match: re.Match[str]) -> str:
        return os.environ.get(match.group(1), "")

    return ENV_VAR_PATTERN.sub(replace, value)


def load_servers(
    config_path: Path, *, exclude: str | None = GATEWAY_OWN_SHORT_NAME
) -> dict[str, ServerConfig]:
    """Loads every [servers.*] entry from servers.toml as a backend to connect to, excluding the
    gateway's own entry (by short name) so it never tries to spawn itself."""
    data = tomllib.loads(config_path.read_text())
    repo_root = config_path.parent

    servers = {}
    for name, entry in data.get("servers", {}).items():
        if name == exclude:
            continue
        servers[name] = ServerConfig(
            name=name,
            description=entry["description"],
            command=entry["command"],
            args=entry.get("args", []),
            cwd=(repo_root / entry["cwd"]).resolve(),
            env={k: _expand_env_vars(v) for k, v in entry.get("env", {}).items()},
        )
    return servers


def to_stdio_params(server: ServerConfig) -> StdioServerParameters:
    command = sys.executable if server.command == "python" else server.command
    return StdioServerParameters(command=command, args=server.args, cwd=server.cwd, env=server.env)
