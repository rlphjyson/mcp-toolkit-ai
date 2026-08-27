import os

HTTP_TIMEOUT_SECONDS = float(os.environ.get("API_CONTRACT_HTTP_TIMEOUT_SECONDS", "10"))
