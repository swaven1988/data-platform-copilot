"""Tenant-isolated AI memory store.

Primary mode uses ChromaDB when installed.
Fallback mode uses deterministic JSONL files to keep tests and local runs stable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4


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
        with p.open("a", encoding="utf-8") as f:
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

