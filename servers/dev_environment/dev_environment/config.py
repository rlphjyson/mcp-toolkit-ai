import os

# tail_log only ever reads files inside this directory (resolved, with traversal rejected) --
# same "safe by construction" posture as sql_query's SELECT-only guard: the tool is safe by
# what it structurally cannot do, not by trying to sanitize an arbitrary path.
LOG_ALLOWED_DIR = os.environ.get("DEV_ENVIRONMENT_LOG_DIR", "./logs")

DEFAULT_TEST_TIMEOUT_SECONDS = float(os.environ.get("DEV_ENVIRONMENT_TEST_TIMEOUT_SECONDS", "120"))
