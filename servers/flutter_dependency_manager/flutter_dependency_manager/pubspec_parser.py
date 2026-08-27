from pathlib import Path
from typing import Any

import yaml


def _normalize_constraint(value: Any) -> str:
    if value is None:
        return "any"
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if "git" in value:
            git_value = value["git"]
            url = git_value.get("url", "") if isinstance(git_value, dict) else git_value
            return f"git:{url}"
        if "path" in value:
            return f"path:{value['path']}"
        if "sdk" in value:
            return f"sdk:{value['sdk']}"
        return "any"
    return str(value)


def parse_pubspec(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"pubspec.yaml not found at {path}")

    data = yaml.safe_load(path.read_text()) or {}
    if "name" not in data:
        raise ValueError(f"pubspec.yaml at {path} has no top-level 'name' key")

    dependencies = {
        name: _normalize_constraint(value) for name, value in (data.get("dependencies") or {}).items()
    }
    dev_dependencies = {
        name: _normalize_constraint(value) for name, value in (data.get("dev_dependencies") or {}).items()
    }

    return {
        "name": data["name"],
        "dependencies": dependencies,
        "dev_dependencies": dev_dependencies,
    }
