import os

# Generated Dart files (*.g.dart, *.freezed.dart, etc.) can be enormous and add nothing a real
# analyzer wouldn't already tell you better -- skip anything past this size so one huge generated
# file can't dominate an index_project call.
MAX_DART_FILE_SIZE_BYTES = int(
    os.environ.get("FLUTTER_PROJECT_INTELLIGENCE_MAX_DART_FILE_SIZE_BYTES", "1000000")
)
