import json
import os
from pathlib import Path
from typing import Dict, Any, List

from .model_spec import ModelSpec

# In-memory cache (fast path)
_MODEL_REGISTRY: Dict[str, Any] = {}

# Default path inside container; can be overridden by env
# IMPORTANT: Ensure this path is writable in your deployment.
_DEFAULT_REGISTRY_PATH = "/tmp/copilot_model_registry.json"


def _registry_path() -> Path:
    p = (os.getenv("COPILOT_MODEL_REGISTRY_PATH") or _DEFAULT_REGISTRY_PATH).strip()
    return Path(p)


def _load_from_disk() -> Dict[str, Any]:
    path = _registry_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def _atomic_write(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _ensure_loaded() -> None:
    global _MODEL_REGISTRY
    if _MODEL_REGISTRY:
        return
    _MODEL_REGISTRY = _load_from_disk()


def register_model(name: str, spec: ModelSpec) -> None:
    _ensure_loaded()
    # Store as plain dict for JSON persistence
    _MODEL_REGISTRY[name] = spec if isinstance(spec, dict) else getattr(spec, "model_dump", lambda: spec)()
    _atomic_write(_registry_path(), _MODEL_REGISTRY)


def get_model(name: str) -> Any:
    _ensure_loaded()
    return _MODEL_REGISTRY[name]


def list_models() -> List[str]:
    _ensure_loaded()
    return sorted(list(_MODEL_REGISTRY.keys()))
