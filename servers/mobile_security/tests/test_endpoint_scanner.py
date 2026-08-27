from mobile_security.endpoint_scanner import find_insecure_endpoints


def test_find_insecure_endpoints_flags_real_http_url(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "api.dart").write_text("final url = 'http://example.com/api';\n")

    findings = find_insecure_endpoints(tmp_path)

    assert len(findings) == 1
    assert findings[0]["url"] == "http://example.com/api"
    assert findings[0]["file"] == "lib/api.dart"


def test_find_insecure_endpoints_ignores_localhost_and_emulator_alias(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "api.dart").write_text(
        "final a = 'http://localhost:8080/api';\n"
        "final b = 'http://127.0.0.1:8080/api';\n"
        "final c = 'http://10.0.2.2:3000/api';\n"
    )

    findings = find_insecure_endpoints(tmp_path)

    assert findings == []


def test_find_insecure_endpoints_skips_generated_dart_files(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "api.g.dart").write_text("final url = 'http://example.com/api';\n")

    findings = find_insecure_endpoints(tmp_path)

    assert findings == []
