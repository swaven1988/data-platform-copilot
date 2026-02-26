from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional
import json

from .models import RuntimeProfile
from .builtins import builtin_profiles


class RuntimeProfileRegistry:
    """Loads deterministic runtime profiles.

    Resolution order:
      1) Built-in profiles (always present)
      2) Optional templates/runtime_profiles/*.json (packaged)
    """

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self._profiles: Dict[str, RuntimeProfile] = {}
        self._load_all()

    def _load_all(self) -> None:
        self._profiles = {p.name: p for p in builtin_profiles()}

        templates_dir = self.project_root / "templates" / "runtime_profiles"
        if not templates_dir.exists():
            return

        for p in sorted(templates_dir.glob("*.json")):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                rp = RuntimeProfile(**data)
                self._profiles[rp.name] = rp
            except Exception:
                # Ignore invalid optional files; deterministic behavior remains.
                continue

    def list_names(self) -> list[str]:
        return sorted(self._profiles.keys())

    def get(self, name: str) -> Optional[RuntimeProfile]:
        return self._profiles.get(name)