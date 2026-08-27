from collections.abc import Callable
from pathlib import PurePosixPath

from flutter_architecture_guardian.violations import Violation


def _is_public_api(imported_path: str, feature: str, public_markers: list[str]) -> bool:
    # classify_feature only returns a feature name when parts[0] == "features" and
    # parts[1] == feature, so what follows is always the path within that feature.
    remainder = PurePosixPath(imported_path).parts[2:]
    if remainder == (f"{feature}.dart",):
        return True
    return any(marker in remainder for marker in public_markers)


def check_feature_first(
    import_graph: dict[str, list[str]],
    classify: Callable[[str], str | None],
    public_markers: list[str],
) -> list[Violation]:
    """Flags imports that reach across feature boundaries into another feature's internals.
    Shared code under core/ or shared/ is always importable. A cross-feature import is only
    allowed through the target feature's `<feature>.dart` barrel file or one of its
    public_markers directories/files."""
    violations = []
    for file, imports in import_graph.items():
        file_feature = classify(file)
        if file_feature is None or file_feature == "core":
            continue
        for imported in imports:
            imported_feature = classify(imported)
            if imported_feature is None or imported_feature == "core":
                continue
            if imported_feature == file_feature:
                continue
            if _is_public_api(imported, imported_feature, public_markers):
                continue
            violations.append(
                Violation(
                    file=file,
                    imported_file=imported,
                    rule="cross_feature_import",
                    message=(
                        f"'{file}' (feature '{file_feature}') imports '{imported}' "
                        f"(feature '{imported_feature}') directly -- cross-feature imports must go "
                        f"through that feature's '{imported_feature}.dart' barrel file or a "
                        f"{'/'.join(public_markers)} directory."
                    ),
                )
            )
    return violations
