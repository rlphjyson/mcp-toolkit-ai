import asyncio
import json
from pathlib import Path
from typing import Annotated

import typer
from mcp import ClientSession
from mcp.shared.exceptions import MCPError
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from mcp_toolkit.client import with_session
from mcp_toolkit.config import find_config_file, load_servers

app = typer.Typer(help="Generic CLI client for the mcp-toolkit-ai MCP servers.")
console = Console()


def _first_leaf(exc: BaseException) -> BaseException:
    # `except* MCPError` prunes the tree to only branches containing a match, but preserves
    # nesting -- `eg.exceptions[0]` can itself still be an ExceptionGroup, not the MCPError leaf.
    if isinstance(exc, BaseExceptionGroup):
        return _first_leaf(exc.exceptions[0])
    return exc


def _run_session(config, fn):
    # MCPError is a protocol-level failure (unknown tool/resource, malformed request) -- distinct
    # from a tool's own ToolError, which surfaces as a normal, non-raising result with
    # result.is_error set. Left uncaught, it propagates as a raw exception and Typer prints a
    # full traceback, which is a poor experience for what's usually a simple user mistake (typo'd
    # tool/resource name). anyio's task groups wrap it in (nested) ExceptionGroups by the time it
    # reaches here -- confirmed by reproducing it directly -- so `except*` is required to match it
    # regardless of nesting depth; a plain `except MCPError` silently does not catch it.
    try:
        return asyncio.run(with_session(config, fn))
    except* MCPError as eg:
        exc = _first_leaf(eg)
        console.print(f"[red]{escape(str(exc))}[/red]")
        raise typer.Exit(code=1) from exc


def _print_tool_result(result) -> None:
    # A tool returning a list produces one TextContent block per item (each independently
    # JSON-encoded), which reads poorly printed block-by-block; a tool returning a dict doesn't
    # populate structured_content at all. Prefer structured_content (the intact, typed result)
    # when the server provided it, and only fall back to walking content blocks when it didn't --
    # confirmed empirically against a live server, since neither behavior is obvious from the
    # method signatures alone.
    if result.structured_content is not None:
        payload = result.structured_content
        if list(payload.keys()) == ["result"]:
            payload = payload["result"]
        console.print_json(json.dumps(payload))
        return

    for block in result.content:
        if block.type == "text":
            console.print(block.text, markup=False)
        else:
            console.print(block)


def _load_server(name: str):
    config_path = find_config_file(Path.cwd())
    servers = load_servers(config_path)
    if name not in servers:
        available = ", ".join(sorted(servers)) or "(none configured)"
        console.print(f"[red]Unknown server '{name}'.[/red] Available: {available}")
        raise typer.Exit(code=1)
    return servers[name]


@app.command("list-servers")
def list_servers() -> None:
    """List the servers registered in servers.toml."""
    config_path = find_config_file(Path.cwd())
    servers = load_servers(config_path)

    table = Table(title=f"Servers ({config_path})")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    for server in servers.values():
        table.add_row(server.name, escape(server.description))
    console.print(table)


@app.command("list-tools")
def list_tools(server: str) -> None:
    """List the tools a server exposes."""
    config = _load_server(server)

    async def _run(session: ClientSession):
        return await session.list_tools()

    result = _run_session(config, _run)

    table = Table(title=f"Tools on '{server}'")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    for tool in result.tools:
        table.add_row(tool.name, escape(tool.description or ""))
    console.print(table)


@app.command("call-tool")
def call_tool(
    server: str,
    tool: str,
    args: Annotated[str, typer.Option("--args", help="JSON object of tool arguments")] = "{}",
) -> None:
    """Call a tool on a server and print its result."""
    config = _load_server(server)
    try:
        arguments = json.loads(args)
    except json.JSONDecodeError as exc:
        console.print(f"[red]--args must be valid JSON: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    async def _run(session: ClientSession):
        return await session.call_tool(tool, arguments)

    result = _run_session(config, _run)
    _print_tool_result(result)
    if result.is_error:
        raise typer.Exit(code=1)


@app.command("list-resources")
def list_resources(server: str) -> None:
    """List the resources a server exposes."""
    config = _load_server(server)

    async def _run(session: ClientSession):
        return await session.list_resources()

    result = _run_session(config, _run)

    table = Table(title=f"Resources on '{server}'")
    table.add_column("URI", style="cyan")
    table.add_column("Name")
    for resource in result.resources:
        table.add_row(escape(str(resource.uri)), escape(resource.name or ""))
    console.print(table)


@app.command("read-resource")
def read_resource(server: str, uri: str) -> None:
    """Read one resource from a server."""
    config = _load_server(server)

    async def _run(session: ClientSession):
        return await session.read_resource(uri)

    result = _run_session(config, _run)

    for content in result.contents:
        if hasattr(content, "text"):
            console.print(content.text, markup=False)
        else:
            console.print(content)


if __name__ == "__main__":
    app()
