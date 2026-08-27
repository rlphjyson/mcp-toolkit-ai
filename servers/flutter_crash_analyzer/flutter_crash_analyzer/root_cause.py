import re

ROOT_CAUSE_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"null check operator used on a null value", re.IGNORECASE), "null_safety"),
    (re.compile(r"type '.*null.*' is not a subtype", re.IGNORECASE), "null_safety"),
    (re.compile(r"renderflex overflowed", re.IGNORECASE), "layout_overflow"),
    (re.compile(r"setstate\(\) called after dispose\(\)", re.IGNORECASE), "lifecycle"),
    (re.compile(r"could not find the correct provider", re.IGNORECASE), "state_management_scope"),
    (re.compile(r"providernotfoundexception", re.IGNORECASE), "state_management_scope"),
    (re.compile(r"socketexception|handshakeexception|timeoutexception", re.IGNORECASE), "network"),
]


def tag_root_causes(exception_type: str, message: str) -> list[str]:
    haystack = f"{exception_type} {message}"
    tags = list(dict.fromkeys(tag for pattern, tag in ROOT_CAUSE_RULES if pattern.search(haystack)))
    return tags or ["unknown"]
