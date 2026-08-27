import re
from pathlib import Path

_SET_CALL_RE = re.compile(r"\.set(?:String|Int|Bool|Double|StringList)\s*\(\s*['\"]([^'\"]+)['\"]")
_SENSITIVE_WORDS = ("token", "password", "secret", "credential", "apikey", "session")

_GENERATED_DART_SUFFIXES = (".g.dart", ".freezed.dart")


def _is_sensitive_key(key: str) -> bool:
    normalized = re.sub(r"[_\-\s]", "", key).lower()
    return any(word in normalized for word in _SENSITIVE_WORDS)


def find_unsafe_storage_usage(project_path: Path) -> list[dict]:
    findings = []
    for path in sorted(project_path.rglob("*.dart")):
        if not path.is_file() or path.name.endswith(_GENERATED_DART_SUFFIXES):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "shared_preferences" not in text and "SharedPreferences" not in text:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            for match in _SET_CALL_RE.finditer(line):
                key = match.group(1)
                if not _is_sensitive_key(key):
                    continue
                findings.append(
                    {
                        "file": str(path.relative_to(project_path)),
                        "line": line_no,
                        "key_expression": key,
                        "reason": (
                            f"SharedPreferences key '{key}' looks sensitive -- use "
                            "flutter_secure_storage instead of shared_preferences for this value."
                        ),
                    }
                )
    return findings
