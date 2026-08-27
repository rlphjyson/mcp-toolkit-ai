import os
import tempfile

DEFAULT_TEST_TIMEOUT_SECONDS = float(os.environ.get("FLUTTER_UI_TESTING_TEST_TIMEOUT_SECONDS", "120"))

# take_screenshot writes PNGs here (both drivers). Defaults to the OS temp dir so nothing is
# left behind in the repo when the server isn't given an explicit directory.
SCREENSHOT_DIR = os.environ.get("FLUTTER_UI_TESTING_SCREENSHOT_DIR", tempfile.gettempdir())
