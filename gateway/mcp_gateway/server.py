import asyncio
import os
import sys
from contextlib import AsyncExitStack
from pathlib import Path

import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from mcp_gateway.aggregator import Gateway
from mcp_gateway.config import find_config_file, load_servers

# Overrides the upward-search-from-cwd config discovery -- lets tests (and anyone launching the
# gateway from outside the repo) point it at a specific servers.toml instead.
CONFIG_PATH_OVERRIDE = os.environ.get("MCP_GATEWAY_CONFIG_PATH")

INSTRUCTIONS = (
    "Aggregates every MCP server registered in servers.toml behind one endpoint. Each backend's "
    "tools are exposed under a namespaced name, '<backend_short_name>__<tool_name>' (e.g. "
    "'flutterintel__index_project') -- call list_tools to see which backends actually connected "
    "and what each one offers; a backend that failed to start is simply absent, not an error."
)


async def _serve(gateway: Gateway) -> None:
    async def on_list_tools(
        _ctx: object, _params: types.PaginatedRequestParams | None
    ) -> types.ListToolsResult:
        return types.ListToolsResult(tools=gateway.list_all_tools())

    async def on_call_tool(
        _ctx: object, params: types.CallToolRequestParams
    ) -> types.CallToolResult | types.InputRequiredResult:
        result = await gateway.call_tool(params.name, params.arguments or {})
        return result

    server: Server = Server(
        "mcp-gateway",
        instructions=INSTRUCTIONS,
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
    )
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


async def main() -> None:
    config_path = Path(CONFIG_PATH_OVERRIDE) if CONFIG_PATH_OVERRIDE else find_config_file(Path.cwd())
    servers = load_servers(config_path)

    async with AsyncExitStack() as stack:
        gateway = Gateway()
        connected, failed = await gateway.connect_all(servers, stack)
        print(
            f"mcp-gateway: connected to {len(connected)} backend(s): {', '.join(connected) or '(none)'}",
            file=sys.stderr,
        )
        if failed:
            print(f"mcp-gateway: skipped unreachable backend(s): {', '.join(failed)}", file=sys.stderr)
        await _serve(gateway)


if __name__ == "__main__":
    asyncio.run(main())
