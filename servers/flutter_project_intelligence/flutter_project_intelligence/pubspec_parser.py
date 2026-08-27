from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ProjectManifest:
    package_name: str
    flutter_sdk_constraint: str | None
    dependencies: dict[str, str] = field(default_factory=dict)
    dev_dependencies: dict[str, str] = field(default_factory=dict)


def _stringify_constraints(raw: dict[str, Any] | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for name, constraint in (raw or {}).items():
        if isinstance(constraint, dict):
            # git/path/sdk dependencies (e.g. `flutter: {sdk: flutter}`) have no plain version
            # range -- fall back to "any" rather than trying to summarize the whole mapping.
            result[name] = str(constraint.get("version", "any"))
        elif constraint is None:
            result[name] = "any"
        else:
            result[name] = str(constraint)
    return result


def parse_pubspec(pubspec_path: Path) -> ProjectManifest:
    """Parses a pubspec.yaml for the project name, SDK constraint, and declared dependencies."""
    data = yaml.safe_load(pubspec_path.read_text(encoding="utf-8")) or {}

    environment = data.get("environment") or {}
    # Modern pubspec.yaml declares only a Dart `sdk:` range; some legacy ones also pin a
    # `flutter:` range directly -- prefer the more specific one when both are present.
    sdk_constraint = environment.get("flutter") or environment.get("sdk")

    return ProjectManifest(
        package_name=str(data.get("name") or ""),
        flutter_sdk_constraint=str(sdk_constraint) if sdk_constraint else None,
        dependencies=_stringify_constraints(data.get("dependencies")),
        dev_dependencies=_stringify_constraints(data.get("dev_dependencies")),
    )
