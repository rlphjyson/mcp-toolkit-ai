import os

DATABASE_URL = os.environ.get("SQL_QUERY_DATABASE_URL", "sqlite:///./data/sample.db")
DEFAULT_MAX_ROWS = int(os.environ.get("SQL_QUERY_DEFAULT_MAX_ROWS", "100"))
HARD_MAX_ROWS = int(os.environ.get("SQL_QUERY_HARD_MAX_ROWS", "1000"))
QUERY_TIMEOUT_SECONDS = float(os.environ.get("SQL_QUERY_TIMEOUT_SECONDS", "10"))
