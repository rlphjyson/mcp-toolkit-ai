import pytest

from flutter_crash_analyzer.stack_trace import parse_stack_trace, to_repo_relative_path

BOXED_TRACE = """\
══╡ EXCEPTION CAUGHT BY WIDGETS LIBRARY ╞══════════════════════
The following _TypeError was thrown building MyWidget(dirty):
Null check operator used on a null value

When the exception was thrown, this was the stack:
#0      MyWidget.build (package:myapp/widgets/my_widget.dart:42:18)
#1      StatelessElement.build (package:flutter/src/widgets/framework.dart:4874:28)
#2      ComponentElement.performRebuild (package:flutter/src/widgets/framework.dart:4757:15)
"""

PLAIN_TRACE = """\
Unhandled exception:
FormatException: Invalid number
#0      parseAmount (package:myapp/utils/money.dart:10:5)
#1      main (package:myapp/main.dart:5:3)
"""


def test_parses_boxed_widgets_exception_format():
    parsed = parse_stack_trace(BOXED_TRACE, project_package_name="myapp")

    assert parsed.exception_type == "_TypeError"
    assert parsed.message == "Null check operator used on a null value"
    assert len(parsed.frames) == 3

    first = parsed.frames[0]
    assert first.index == 0
    assert first.function == "MyWidget.build"
    assert first.file == "package:myapp/widgets/my_widget.dart"
    assert first.line == 42
    assert first.column == 18
    assert first.is_project_code is True

    assert parsed.frames[1].is_project_code is False


def test_parses_plain_unhandled_exception_format():
    parsed = parse_stack_trace(PLAIN_TRACE, project_package_name="myapp")

    assert parsed.exception_type == "FormatException"
    assert parsed.message == "Invalid number"
    assert len(parsed.frames) == 2
    assert parsed.frames[0].function == "parseAmount"
    assert parsed.frames[0].file == "package:myapp/utils/money.dart"
    assert parsed.frames[0].line == 10
    assert parsed.frames[0].column == 5
    assert parsed.frames[0].is_project_code is True
    assert parsed.frames[1].is_project_code is True


def test_relative_project_path_is_project_code():
    trace = "Unhandled exception:\nStateError: bad state\n#0      foo (lib/utils/foo.dart:3:1)\n"
    parsed = parse_stack_trace(trace)
    assert parsed.frames[0].is_project_code is True
    assert parsed.frames[0].file == "lib/utils/foo.dart"


def test_dart_core_frame_is_not_project_code():
    trace = "Unhandled exception:\nStateError: bad state\n#0      foo (dart:core/errors.dart:280:28)\n"
    parsed = parse_stack_trace(trace)
    assert parsed.frames[0].is_project_code is False


def test_package_frame_without_project_package_name_is_not_project_code():
    trace = "Unhandled exception:\nStateError: bad state\n#0      foo (package:myapp/foo.dart:3:1)\n"
    parsed = parse_stack_trace(trace)
    assert parsed.frames[0].is_project_code is False


def test_no_column_frame_is_parsed():
    trace = "Unhandled exception:\nStateError: bad state\n#0      foo (package:myapp/foo.dart:3)\n"
    parsed = parse_stack_trace(trace, project_package_name="myapp")
    assert parsed.frames[0].line == 3
    assert parsed.frames[0].column is None


def test_empty_trace_text_raises_value_error():
    with pytest.raises(ValueError, match="empty"):
        parse_stack_trace("")


def test_unparseable_garbage_raises_value_error():
    with pytest.raises(ValueError, match="Could not find"):
        parse_stack_trace("this is not a stack trace at all, just some prose")


def test_to_repo_relative_path_maps_package_uri_to_lib():
    assert (
        to_repo_relative_path("package:myapp/widgets/my_widget.dart", "myapp")
        == "lib/widgets/my_widget.dart"
    )


def test_to_repo_relative_path_passes_through_relative_paths():
    assert to_repo_relative_path("lib/widgets/my_widget.dart", "myapp") == "lib/widgets/my_widget.dart"


def test_to_repo_relative_path_passes_through_when_no_project_package_name():
    assert (
        to_repo_relative_path("package:myapp/widgets/my_widget.dart", None)
        == "package:myapp/widgets/my_widget.dart"
    )
