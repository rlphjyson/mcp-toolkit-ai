from collections.abc import Callable
from functools import wraps
from typing import TypeVar

import sqlalchemy as sa
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from sql_query import db
from sql_query.config import DEFAULT_MAX_ROWS

server = MCPServer(
    "sql-query",
    instructions=(
        "Safe, read-only SQL querying. Only single SELECT statements are ever executed -- "
        "list_tables and describe_table first, then run_query."
    ),
)

T = TypeVar("T")

# By default, an MCPServer tool that raises anything other than its own ToolError is treated as
# an unexpected crash: the message is logged server-side but replaced with a generic one for the
# caller (confirmed by reading mcp.server.mcpserver.tools.base's exception handling -- a
# deliberate, sensible security default against leaking internals). validate_select_only,
# db.describe_table, db.run_query, and the underlying DB driver all raise plain ValueError /
# QueryTimeoutError / SQLAlchemyError for conditions that are entirely safe and useful to show
# the caller (bad table name, non-SELECT statement, query timeout, bad SQL syntax) -- this
# decorator is what actually surfaces those messages instead of a generic one.
KNOWN_SAFE_ERRORS = (ValueError, db.QueryTimeoutError, sa.exc.SQLAlchemyError)


def surface_known_errors(fn: Callable[..., T]) -> Callable[..., T]:
    @wraps(fn)
    def wrapper(*args: object, **kwargs: object) -> T:
        try:
            return fn(*args, **kwargs)
        except KNOWN_SAFE_ERRORS as exc:
            raise ToolError(str(exc)) from exc

    return wrapper


@server.tool()
def list_tables() -> list[str]:
    """Lists tables in the configured database."""
    return db.list_tables()


@server.tool()
@surface_known_errors
def describe_table(table: str) -> list[dict]:
    """Column names, types, and nullability for one table."""
    columns = db.describe_table(table)
    return [{"name": c.name, "type": c.type, "nullable": c.nullable} for c in columns]


@server.tool()
@surface_known_errors
def run_query(sql: str, max_rows: int = DEFAULT_MAX_ROWS) -> dict:
    """Executes a single read-only SELECT statement. Rejects anything else (multiple statements,
    INSERT/UPDATE/DELETE/DDL) before it ever reaches the database. Results are capped at
    max_rows; `truncated` is true if there were more rows than that."""
    result = db.run_query(sql, max_rows)
    return {"columns": result.columns, "rows": result.rows, "truncated": result.truncated}


if __name__ == "__main__":
    server.run()
