import pytest

from mobile_security.android_permissions import check_android_permissions

MANIFEST_XML = """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-permission android:name="android.permission.INTERNET"/>
    <uses-permission android:name="android.permission.CAMERA"/>
</manifest>
"""


def _write_manifest(project_path):
    manifest_dir = project_path / "android" / "app" / "src" / "main"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "AndroidManifest.xml").write_text(MANIFEST_XML)


def test_check_android_permissions_lists_and_flags(tmp_path):
    _write_manifest(tmp_path)

    result = check_android_permissions(tmp_path)

    assert result["all_permissions"] == [
        "android.permission.INTERNET",
        "android.permission.CAMERA",
    ]
    assert result["flagged_permissions"] == ["android.permission.CAMERA"]


def test_check_android_permissions_raises_when_manifest_missing(tmp_path):
    with pytest.raises(FileNotFoundError, match="AndroidManifest.xml"):
        check_android_permissions(tmp_path)
