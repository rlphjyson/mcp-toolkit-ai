import re
from pathlib import Path

_HTTP_URL_RE = re.compile(r"http://[^\s'\"<>]+")

# http://10.0.2.2 is the well-known Android-emulator-to-host alias -- a legitimate dev
# convenience, not a real finding, same as localhost/loopback.
_ALLOWED_HOSTS = ("http://localhost", "http://127.0.0.1", "http://10.0.2.2")

_GENERATED_DART_SUFFIXES = (".g.dart", ".freezed.dart")


def find_insecure_endpoints(project_path: Path) -> list[dict]:
    findings = []
    for path in sorted(project_path.rglob("*.dart")):
        if not path.is_file() or path.name.endswith(_GENERATED_DART_SUFFIXES):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_no, line in enumerate(text.splitlines(), start=1):
            for match in _HTTP_URL_RE.finditer(line):
                url = match.group(0)
                if url.startswith(_ALLOWED_HOSTS):
                    continue
                findings.append(
                    {
                        "file": str(path.relative_to(project_path)),
                        "line": line_no,
                        "url": url,
                    }
                )
    return findings
