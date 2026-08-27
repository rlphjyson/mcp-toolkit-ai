import xml.etree.ElementTree as ET
from pathlib import Path

_ANDROID_NS_NAME = "{http://schemas.android.com/apk/res/android}name"

SENSITIVE_PERMISSIONS = {
    "android.permission.ACCESS_FINE_LOCATION",
    "android.permission.ACCESS_BACKGROUND_LOCATION",
    "android.permission.READ_CONTACTS",
    "android.permission.READ_SMS",
    "android.permission.RECORD_AUDIO",
    "android.permission.CAMERA",
    "android.permission.READ_EXTERNAL_STORAGE",
    "android.permission.MANAGE_EXTERNAL_STORAGE",
    "android.permission.READ_CALL_LOG",
    "android.permission.SYSTEM_ALERT_WINDOW",
}


def check_android_permissions(project_path: Path) -> dict:
    manifest_path = project_path / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"AndroidManifest.xml not found at {manifest_path}")

    root = ET.parse(manifest_path).getroot()
    all_permissions = [
        name
        for elem in root.iter("uses-permission")
        if (name := elem.get(_ANDROID_NS_NAME)) is not None
    ]
    flagged_permissions = [p for p in all_permissions if p in SENSITIVE_PERMISSIONS]

    return {"all_permissions": all_permissions, "flagged_permissions": flagged_permissions}
