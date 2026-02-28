"""Tenant-isolated AI memory store.

Primary mode uses ChromaDB when installed.
Fallback mode uses deterministic JSONL files to keep tests and local runs stable.
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Generator, List
from uuid import uuid4

try:
    import fcntl as _fcntl

    _HAS_FCNTL = True
except ImportError:
    _HAS_FCNTL = False
    logging.getLogger("copilot.ai.memory").warning(
        "fcntl not available (non-POSIX). Concurrent memory writes are not safe on this platform."
    )


@contextmanager
def _locked_append(path: Path) -> Generator:
    """Open file for append with exclusive flock (POSIX only)."""
    with open(path, "a", encoding="utf-8") as fh:
        if _HAS_FCNTL:
            _fcntl.flock(fh, _fcntl.LOCK_EX)
        try:
            yield fh
        finally:
            if _HAS_FCNTL:
                _fcntl.flock(fh, _fcntl.LOCK_UN)


@dataclass
class MemoryHit:
    id: str
    text: str
    metadata: Dict[str, Any]
    score: float


def _token_overlap_score(query: str, text: str) -> float:
    q = {t for t in (query or "").lower().split() if t}
    d = {t for t in (text or "").lower().split() if t}
    if not q:
        return 0.0
    return round(len(q & d) / max(1, len(q)), 4)


class TenantMemoryStore:
    def __init__(self, *, workspace_root: Path):
        self.workspace_root = workspace_root
        self.root = self.workspace_root / ".copilot" / "ai_memory"
        self.root.mkdir(parents=True, exist_ok=True)

    def _tenant_file(self, tenant: str, collection: str) -> Path:
        t = (tenant or "default").strip() or "default"
        c = (collection or "default").strip() or "default"
        td = self.root / t
        td.mkdir(parents=True, exist_ok=True)
        return td / f"{c}.jsonl"

    def add_document(
        self,
        *,
        tenant: str,
        collection: str,
        text: str,
        metadata: Dict[str, Any] | None = None,
        doc_id: str | None = None,
    ) -> str:
        p = self._tenant_file(tenant, collection)
        did = doc_id or uuid4().hex
        row = {
            "id": did,
            "text": text,
            "metadata": metadata or {},
        }
        with _locked_append(p) as f:
            f.write(json.dumps(row, sort_keys=True) + "\n")
        return did

    def _read_all(self, *, tenant: str, collection: str) -> List[Dict[str, Any]]:
        p = self._tenant_file(tenant, collection)
        if not p.exists():
            return []
        out: List[Dict[str, Any]] = []
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                try:
                    obj = json.loads(s)
                except Exception:
                    continue
                if isinstance(obj, dict):
                    out.append(obj)
        return out

    def search(
        self,
        *,
        tenant: str,
        collection: str,
        query: str,
        top_k: int = 5,
    ) -> List[MemoryHit]:
        rows = self._read_all(tenant=tenant, collection=collection)
        scored: List[MemoryHit] = []
        for r in rows:
            txt = str(r.get("text") or "")
            score = _token_overlap_score(query, txt)
            if score <= 0:
                continue
            scored.append(
                MemoryHit(
                    id=str(r.get("id") or ""),
                    text=txt,
                    metadata=r.get("metadata") or {},
                    score=score,
                )
            )
        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[: max(1, int(top_k))]

