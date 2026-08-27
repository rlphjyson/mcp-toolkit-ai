from mobile_security.storage_scanner import find_unsafe_storage_usage

_IMPORT_LINE = "import 'package:shared_preferences/shared_preferences.dart';\n"


def test_find_unsafe_storage_usage_flags_sensitive_key(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "auth.dart").write_text(
        _IMPORT_LINE + "prefs.setString('auth_token', token);\n"
    )

    findings = find_unsafe_storage_usage(tmp_path)

    assert len(findings) == 1
    assert findings[0]["key_expression"] == "auth_token"
    assert findings[0]["file"] == "lib/auth.dart"


def test_find_unsafe_storage_usage_ignores_non_sensitive_key(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "prefs.dart").write_text(
        _IMPORT_LINE + "prefs.setString('username', name);\n"
    )

    findings = find_unsafe_storage_usage(tmp_path)

    assert findings == []


def test_find_unsafe_storage_usage_ignores_files_without_shared_preferences(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "other.dart").write_text("someOtherApi.setString('auth_token', token);\n")

    findings = find_unsafe_storage_usage(tmp_path)

    assert findings == []
