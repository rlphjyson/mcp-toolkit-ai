import os

# Files larger than this are skipped during regex scans -- a static scanner has no business
# reading multi-megabyte generated assets or bundled data files line by line.
MAX_SCAN_FILE_SIZE_BYTES = int(
    os.environ.get("MOBILE_SECURITY_MAX_SCAN_FILE_SIZE_BYTES", str(2 * 1024 * 1024))
)
