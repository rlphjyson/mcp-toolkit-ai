import os
import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from mcp.client.stdio import StdioServerParameters

CONFIG_FILENAME = "servers.toml"
ENV_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


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
    config -- lets the CLI be run from any directory inside the repo, not just the root."""
    current = start.resolve()
    for candidate in (current, *current.parents):
        config_path = candidate / CONFIG_FILENAME
        if config_path.is_file():
            return config_path
    raise FileNotFoundError(
        f"Could not find {CONFIG_FILENAME} in {start} or any parent directory."
    )


def _expand_env_vars(value: str) -> str:
    """Expands ${VAR_NAME} references against the CLI's own environment, so servers.toml can
    reference e.g. a GitHub token without the secret itself living in the file."""

    def replace(match: re.Match[str]) -> str:
        return os.environ.get(match.group(1), "")

    return ENV_VAR_PATTERN.sub(replace, value)


def load_servers(config_path: Path) -> dict[str, ServerConfig]:
    data = tomllib.loads(config_path.read_text())
    repo_root = config_path.parent

    servers = {}
    for name, entry in data.get("servers", {}).items():
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
