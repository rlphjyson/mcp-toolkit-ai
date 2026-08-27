import os

DEFAULT_LCOV_PATH = os.environ.get("FLUTTER_TEST_COVERAGE_LCOV_PATH", "coverage/lcov.info")
DEFAULT_LOW_COVERAGE_THRESHOLD = float(os.environ.get("FLUTTER_TEST_COVERAGE_THRESHOLD", "50.0"))
