from pathlib import PurePosixPath

CLEAN_LAYERS = ("presentation", "domain", "data")


def classify_clean_layer(rel_path: str) -> str | None:
    """Which Clean Architecture layer a project-relative (relative to lib/) file sits under, by
    looking for a `presentation/`, `domain/`, or `data/` path segment anywhere in it -- these
    directories may be nested under a `lib/<feature>/` grouping. None if the file is under none
    of them."""
    parts = PurePosixPath(rel_path).parts
    for layer in CLEAN_LAYERS:
        if layer in parts:
            return layer
    return None


def classify_feature(rel_path: str) -> str | None:
    """Which feature a project-relative (relative to lib/) file belongs to, from a
    `features/<name>/` segment. Returns "core" for anything under `core/` or `shared/` (always
    importable by any feature), or None if the file matches neither shape."""
    parts = PurePosixPath(rel_path).parts
    if not parts:
        return None
    if parts[0] == "features" and len(parts) > 2:
        return parts[1]
    if parts[0] in ("core", "shared"):
        return "core"
    return None
