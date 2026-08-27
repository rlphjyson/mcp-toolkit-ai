from mobile_security.secret_scanner import scan_for_secrets


def test_scan_for_secrets_finds_aws_key_in_dart_file(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "config.dart").write_text('const awsKey = "AKIAABCDEFGHIJKLMNOP";\n')

    findings = scan_for_secrets(tmp_path)

    assert len(findings) == 1
    assert findings[0]["pattern_name"] == "aws_access_key"
    assert findings[0]["file"] == "lib/config.dart"
    assert findings[0]["line"] == 1


def test_scan_for_secrets_finds_generic_api_key_assignment(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "config.dart").write_text('final apiKey = "sk_live_1234567890abcdef";\n')

    findings = scan_for_secrets(tmp_path)

    assert any(f["pattern_name"] == "generic_api_key" for f in findings)


def test_scan_for_secrets_redacts_matched_text(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "config.dart").write_text('const awsKey = "AKIAABCDEFGHIJKLMNOP";\n')

    findings = scan_for_secrets(tmp_path)

    redacted = findings[0]["matched_text_redacted"]
    assert "AKIAABCDEFGHIJKLMNOP" not in redacted
    assert "..." in redacted


def test_scan_for_secrets_skips_generated_dart_files(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "model.g.dart").write_text('const awsKey = "AKIAABCDEFGHIJKLMNOP";\n')
    (lib / "model.freezed.dart").write_text('const awsKey = "AKIAABCDEFGHIJKLMNOP";\n')

    findings = scan_for_secrets(tmp_path)

    assert findings == []


def test_scan_for_secrets_scans_env_files(tmp_path):
    (tmp_path / ".env").write_text("AWS_SECRET_ACCESS_KEY=AKIAABCDEFGHIJKLMNOP\n")

    findings = scan_for_secrets(tmp_path)

    assert len(findings) == 1
    assert findings[0]["file"] == ".env"


def test_scan_for_secrets_finds_private_key_header(tmp_path):
    (tmp_path / "cert.properties").write_text("-----BEGIN RSA PRIVATE KEY-----\nabc\n")

    findings = scan_for_secrets(tmp_path)

    assert any(f["pattern_name"] == "private_key" for f in findings)
