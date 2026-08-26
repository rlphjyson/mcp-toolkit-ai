from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import TypeVar

from mcp import ClientSession
from mcp.client.stdio import stdio_client

from mcp_toolkit.config import ServerConfig, to_stdio_params

T = TypeVar("T")


@asynccontextmanager
async def connect(server: ServerConfig):
    params = to_stdio_params(server)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def with_session(server: ServerConfig, fn: Callable[[ClientSession], Awaitable[T]]) -> T:
    """Spawns the server subprocess, opens an MCP session, runs `fn`, then tears it down --
    the shape every CLI command needs, factored out so commands are just `fn`."""
    async with connect(server) as session:
        return await fn(session)
