from flutter_crash_analyzer.root_cause import tag_root_causes


def test_null_check_operator_tags_null_safety():
    assert tag_root_causes("_TypeError", "Null check operator used on a null value") == ["null_safety"]


def test_null_subtype_tags_null_safety():
    assert tag_root_causes("TypeError", "type 'Null' is not a subtype of type 'int'") == ["null_safety"]


def test_render_flex_overflow_tags_layout_overflow():
    assert tag_root_causes("FlutterError", "A RenderFlex overflowed by 42 pixels") == ["layout_overflow"]


def test_setstate_after_dispose_tags_lifecycle():
    assert tag_root_causes("FlutterError", "setState() called after dispose()") == ["lifecycle"]


def test_provider_scope_error_tags_state_management_scope():
    assert tag_root_causes("Error", "Could not find the correct Provider<MyModel>") == [
        "state_management_scope"
    ]


def test_provider_not_found_exception_tags_state_management_scope():
    assert tag_root_causes("ProviderNotFoundException", "no provider found") == [
        "state_management_scope"
    ]


def test_socket_exception_tags_network():
    assert tag_root_causes("SocketException", "Connection refused") == ["network"]


def test_timeout_exception_tags_network():
    assert tag_root_causes("TimeoutException", "Future not completed") == ["network"]


def test_unmatched_exception_tags_unknown():
    assert tag_root_causes("MyCustomException", "something bespoke went wrong") == ["unknown"]


def test_returns_all_matching_tags_without_duplicates():
    tags = tag_root_causes("SocketException", "SocketException: Connection refused")
    assert tags == ["network"]
