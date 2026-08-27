from collections.abc import Callable

from flutter_architecture_guardian.violations import Violation

# Clean Architecture's dependency rule: dependencies point inward, domain is innermost.
# (source_layer, imported_layer) -> (rule, direction the import should have gone instead).
_FORBIDDEN_DIRECTIONS = {
    ("domain", "presentation"): (
        "domain_imports_presentation",
        "domain must not depend on presentation -- presentation may depend on domain, not the reverse",
    ),
    ("domain", "data"): (
        "domain_imports_data",
        "domain must not depend on data -- data may depend on domain to implement its interfaces, "
        "not the reverse",
    ),
    ("presentation", "data"): (
        "presentation_imports_data",
        "presentation must not depend on data directly -- it should go through domain interfaces instead",
    ),
}


def check_clean_architecture(
    import_graph: dict[str, list[str]], classify: Callable[[str], str | None]
) -> list[Violation]:
    """Flags imports that break Clean Architecture's inward dependency rule between the
    presentation, domain, and data layers."""
    violations = []
    for file, imports in import_graph.items():
        file_layer = classify(file)
        if file_layer is None:
            continue
        for imported in imports:
            imported_layer = classify(imported)
            if imported_layer is None or imported_layer == file_layer:
                continue
            forbidden = _FORBIDDEN_DIRECTIONS.get((file_layer, imported_layer))
            if forbidden is None:
                continue
            rule, direction = forbidden
            violations.append(
                Violation(
                    file=file,
                    imported_file=imported,
                    rule=rule,
                    message=f"'{file}' ({file_layer}) imports '{imported}' ({imported_layer}): {direction}.",
                )
            )
    return violations
