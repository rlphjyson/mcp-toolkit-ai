import re
from pathlib import Path

from mobile_security.config import MAX_SCAN_FILE_SIZE_BYTES

SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    (
        "generic_api_key",
        re.compile(
            r"(?i)(api[_-]?key|apikey|secret[_-]?key|access[_-]?token)\s*[:=]\s*"
            r"['\"][A-Za-z0-9_\-]{16,}['\"]"
        ),
    ),
    ("google_api_key", re.compile(r"AIza[0-9A-Za-z\-_]{35}")),
    ("bearer_token", re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{20,}")),
    ("private_key", re.compile(r"-----BEGIN (RSA |EC )?PRIVATE KEY-----")),
    ("slack_token", re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}")),
]

_GENERATED_DART_SUFFIXES = (".g.dart", ".freezed.dart")
_EXTRA_SCAN_SUFFIXES = {".env", ".json", ".plist", ".xml", ".gradle", ".properties"}


def _is_scannable(path: Path) -> bool:
    name = path.name
    if name.endswith(_GENERATED_DART_SUFFIXES):
        return False
    if name.endswith(".dart"):
        return True
    return path.suffix in _EXTRA_SCAN_SUFFIXES or name == ".env" or name.startswith(".env.")


def _redact(matched_text: str) -> str:
    if len(matched_text) <= 8:
        return "*" * len(matched_text)
    return f"{matched_text[:4]}...{matched_text[-4:]}"


def scan_for_secrets(project_path: Path) -> list[dict]:
    findings = []
    for path in sorted(project_path.rglob("*")):
        if not path.is_file() or not _is_scannable(path):
            continue
        if path.stat().st_size > MAX_SCAN_FILE_SIZE_BYTES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_no, line in enumerate(text.splitlines(), start=1):
            for pattern_name, pattern in SECRET_PATTERNS:
                for match in pattern.finditer(line):
                    findings.append(
                        {
                            "file": str(path.relative_to(project_path)),
                            "line": line_no,
                            "pattern_name": pattern_name,
                            "matched_text_redacted": _redact(match.group(0)),
                        }
                    )
    return findings
