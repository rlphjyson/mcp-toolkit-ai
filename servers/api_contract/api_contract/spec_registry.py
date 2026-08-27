import hashlib
import json

_SPECS: dict[str, dict] = {}


def _spec_id_for(spec: dict) -> str:
    """Deterministic short id for a spec's content -- registering the same spec content twice
    reuses the same id, matching the "index once, operate after" pattern used by
    codebase_intelligence's repo_registry."""
    canonical = json.dumps(spec, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:12]


def register_spec(spec: dict) -> str:
    spec_id = _spec_id_for(spec)
    _SPECS[spec_id] = spec
    return spec_id


def get_spec(spec_id: str) -> dict:
    if spec_id not in _SPECS:
        raise ValueError(f"Unknown spec_id '{spec_id}'. Call load_openapi_spec first.")
    return _SPECS[spec_id]
