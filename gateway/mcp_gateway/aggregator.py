import sys
from contextlib import AsyncExitStack
from dataclasses import dataclass

import mcp.types as types
from mcp import ClientSession
from mcp.client.stdio import stdio_client

from mcp_gateway.config import ServerConfig, to_stdio_params

# Separator between a backend's short name and its own tool name in the gateway's namespaced
# tool names, e.g. "flutterintel__index_project". Chosen because MCP tool names are conventionally
# snake_case, so "__" reads unambiguously as a namespace boundary rather than part of a tool's own
# name (which never contains a double underscore in this repo's servers).
NAMESPACE_SEPARATOR = "__"


def namespaced_name(short_name: str, tool_name: str) -> str:
    return f"{short_name}{NAMESPACE_SEPARATOR}{tool_name}"


def split_namespaced_name(full_name: str) -> tuple[str, str]:
    """Splits "shortname__tool_name" into ("shortname", "tool_name"). Raises ValueError if the
    name has no namespace separator at all -- a clearly malformed tool name, not just an unknown
    backend (that distinction is left to the caller, which knows the actual backend registry)."""
    if NAMESPACE_SEPARATOR not in full_name:
        raise ValueError(
            f"'{full_name}' is not a namespaced gateway tool name "
            f"(expected '<backend>{NAMESPACE_SEPARATOR}<tool>')"
        )
    short_name, _, tool_name = full_name.partition(NAMESPACE_SEPARATOR)
    return short_name, tool_name


def _error_result(message: str) -> types.CallToolResult:
    return types.CallToolResult(content=[types.TextContent(type="text", text=message)], is_error=True)


@dataclass
class BackendHandle:
    short_name: str
    description: str
    session: ClientSession
    tools: list[types.Tool]


class Gateway:
    """Aggregates every backend MCP server registered in servers.toml behind one MCP endpoint:
    lists their tools under namespaced names and routes calls back to the right backend session.
    Backend connections are opened once (via connect_all) and held open for the gateway's whole
    lifetime, rather than being spawned per call -- the same persistent-session shape the CLI
    uses per-command, just kept alive across many calls instead of one."""

    def __init__(self) -> None:
        self._backends: dict[str, BackendHandle] = {}

    async def connect_all(
        self, servers: dict[str, ServerConfig], stack: AsyncExitStack
    ) -> tuple[list[str], list[str]]:
        """Connects to every backend, entering its stdio_client/ClientSession context managers
        into `stack` so they stay open until the stack itself closes. A backend that fails to
        start (missing interpreter, crashes on startup, etc.) is skipped rather than aborting the
        whole gateway -- one broken backend shouldn't take down every other one. Returns
        (connected_short_names, failed_short_names)."""
        connected: list[str] = []
        failed: list[str] = []
        for short_name, config in servers.items():
            try:
                params = to_stdio_params(config)
                read, write = await stack.enter_async_context(stdio_client(params))
                session = await stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                tools_result = await session.list_tools()
            except Exception as exc:  # noqa: BLE001 -- a broken backend must not crash the gateway
                print(f"mcp-gateway: could not connect to backend '{short_name}': {exc}", file=sys.stderr)
                failed.append(short_name)
                continue
            self._backends[short_name] = BackendHandle(
                short_name=short_name,
                description=config.description,
                session=session,
                tools=list(tools_result.tools),
            )
            connected.append(short_name)
        return connected, failed

    def list_all_tools(self) -> list[types.Tool]:
        aggregated: list[types.Tool] = []
        for backend in self._backends.values():
            for tool in backend.tools:
                aggregated.append(
                    types.Tool(
                        name=namespaced_name(backend.short_name, tool.name),
                        title=tool.title,
                        description=f"[{backend.short_name}] {tool.description or ''}".strip(),
                        input_schema=tool.input_schema,
                        output_schema=tool.output_schema,
                        annotations=tool.annotations,
                    )
                )
        return aggregated

    async def call_tool(self, full_name: str, arguments: dict) -> types.CallToolResult:
        try:
            short_name, tool_name = split_namespaced_name(full_name)
        except ValueError as exc:
            return _error_result(str(exc))

        backend = self._backends.get(short_name)
        if backend is None:
            known = ", ".join(sorted(self._backends)) or "(none connected)"
            return _error_result(f"Unknown gateway backend '{short_name}'. Connected backends: {known}")

        try:
            return await backend.session.call_tool(tool_name, arguments)
        except Exception as exc:  # noqa: BLE001 -- surface the real failure instead of crashing
            return _error_result(f"Backend '{short_name}' call to '{tool_name}' failed: {exc}")
