import sqlparse


def validate_select_only(sql: str) -> None:
    """Raises ValueError unless `sql` is exactly one SELECT (or WITH ... SELECT / CTE)
    statement. Rejects empty input, multiple statements (semicolon-separated -- including a
    SELECT followed by something destructive), and any non-SELECT statement type (INSERT,
    UPDATE, DELETE, DROP, ALTER, etc).

    This is the tool's actual safety boundary -- run_query never rewrites or sanitizes the SQL
    text itself, it only ever executes what passes this check unchanged.
    """
    statements = [s for s in sqlparse.parse(sql) if s.token_first(skip_cm=True) is not None]

    if len(statements) == 0:
        raise ValueError("No SQL statement found.")
    if len(statements) > 1:
        raise ValueError("Only a single SQL statement is allowed.")

    statement_type = statements[0].get_type()
    if statement_type != "SELECT":
        raise ValueError(f"Only SELECT statements are allowed (got {statement_type}).")
