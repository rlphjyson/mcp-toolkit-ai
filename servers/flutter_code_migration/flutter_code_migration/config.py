import os

# Glob (relative to the scanned project root) used to find Dart source files -- overridable so a
# caller can point this at a non-standard layout without editing code.
LIB_GLOB_PATTERN = os.environ.get("FLUTTER_CODE_MIGRATION_LIB_GLOB", "lib/**/*.dart")
