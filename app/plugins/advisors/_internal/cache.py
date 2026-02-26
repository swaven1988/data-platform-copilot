from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .types import AdvisorFinding
from .config import AdvisorsRunConfig


@dataclass
class CacheEntry:
    created_at: float
    findings: List[AdvisorFinding]
    plan: Any


class AdvisorsRunCache:
    def __init__(self, max_entries: int = 128, ttl_seconds: int = 300):
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self._store: Dict[str, CacheEntry] = {}
        self.hits = 0
        self.misses = 0

    def _evict_if_needed(self) -> None:
        if len(self._store) <= self.max_entries:
            return
        # evict oldest
        oldest_key = min(self._store.items(), key=lambda kv: kv[1].created_at)[0]
        self._store.pop(oldest_key, None)

    def _is_expired(self, entry: CacheEntry) -> bool:
        return (time.time() - entry.created_at) > self.ttl_seconds

    def get(self, key: str) -> Optional[CacheEntry]:
        entry = self._store.get(key)
        if not entry:
            self.misses += 1
            return None
        if self._is_expired(entry):
            self._store.pop(key, None)
            self.misses += 1
            return None
        self.hits += 1
        return entry

    def set(self, key: str, findings: List[AdvisorFinding], plan: Any) -> None:
        self._store[key] = CacheEntry(created_at=time.time(), findings=findings, plan=plan)
        self._evict_if_needed()


def make_cache_key(
    *,
    intent: str | None,
    paths: list[str] | None,
    cfg: AdvisorsRunConfig,
    context: Dict[str, Any],
    plugins_fingerprint: str,
) -> str:
    payload = {
        "intent": intent,
        "paths": paths or [],
        "enabled": cfg.enabled,
        "disabled": cfg.disabled,
        "options": cfg.options,
        "spec": context.get("spec"),
        "plugins_fingerprint": plugins_fingerprint,
        "workspace_head": context.get("workspace_head"),
        "upstream_head": context.get("upstream_head"),
    }
    raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
