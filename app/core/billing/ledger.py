from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

try:
    import fcntl as _fcntl
    _HAS_FCNTL = True
except ImportError:
    _HAS_FCNTL = False
    logging.getLogger("copilot.locking").warning(
        "fcntl not available (non-POSIX). File locking is disabled. "
        "Do not run concurrent ledger writes in production on this platform."
    )


@contextmanager
def _locked_file(path: Path, mode: str) -> Generator:
    """Open a file and apply an exclusive flock (POSIX only). No-op on Windows."""
    with open(path, mode, encoding="utf-8") as fh:
        if _HAS_FCNTL:
            _fcntl.flock(fh, _fcntl.LOCK_EX)
        try:
            yield fh
        finally:
            if _HAS_FCNTL:
                _fcntl.flock(fh, _fcntl.LOCK_UN)



def utc_month_key(dt: Optional[datetime] = None) -> str:
    d = dt or datetime.now(timezone.utc)
    return f"{d.year:04d}-{d.month:02d}"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _billing_root_from_workspace(workspace_dir: Path) -> Path:
    root = workspace_dir.parent / ".copilot" / "billing"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _ledger_path(workspace_dir: Path) -> Path:
    return _billing_root_from_workspace(workspace_dir) / "ledger.json"


@dataclass(frozen=True)
class LedgerEntry:
    entry_id: str
    tenant: str
    month: str
    job_name: str
    build_id: str
    estimated_cost_usd: float
    ts: str

    # Phase 12.2: actuals (optional)
    actual_cost_usd: Optional[float] = None
    actual_runtime_seconds: Optional[float] = None
    finished_ts: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "tenant": self.tenant,
            "month": self.month,
            "job_name": self.job_name,
            "build_id": self.build_id,
            "estimated_cost_usd": self.estimated_cost_usd,
            "ts": self.ts,
            "actual_cost_usd": self.actual_cost_usd,
            "actual_runtime_seconds": self.actual_runtime_seconds,
            "finished_ts": self.finished_ts,
        }


class LedgerStore:
    def __init__(self, *, workspace_dir: Path):
        self.workspace_dir = workspace_dir

    def _load(self) -> Dict[str, Any]:
        p = _ledger_path(self.workspace_dir)
        if not p.exists():
            return {"kind": "ledger", "entries": []}
        try:
            with _locked_file(p, "r") as fh:
                return json.loads(fh.read())
        except Exception:
            return {"kind": "ledger", "entries": []}

    def _save(self, obj: Dict[str, Any]) -> None:
        p = _ledger_path(self.workspace_dir)
        p.parent.mkdir(parents=True, exist_ok=True)
        with _locked_file(p, "w") as fh:
            fh.write(json.dumps(obj, indent=2, sort_keys=True))


    def upsert_estimate(
        self,
        *,
        tenant: str,
        month: str,
        job_name: str,
        build_id: str,
        estimated_cost_usd: float,
    ) -> LedgerEntry:
        # Idempotency key: tenant + build + job
        entry_id = f"{tenant}:{build_id}:{job_name}"
        entry = LedgerEntry(
            entry_id=entry_id,
            tenant=tenant,
            month=month,
            job_name=job_name,
            build_id=build_id,
            estimated_cost_usd=float(estimated_cost_usd),
            ts=_utc_now_iso(),
        )

        obj = self._load()
        entries = obj.get("entries", [])
        if not isinstance(entries, list):
            entries = []

        # replace if existing, else append
        replaced = False
        for i, e in enumerate(entries):
            if isinstance(e, dict) and e.get("entry_id") == entry_id:
                entries[i] = entry.to_dict()
                replaced = True
                break

        if not replaced:
            entries.append(entry.to_dict())

        obj["kind"] = "ledger"
        obj["entries"] = entries
        self._save(obj)
        return entry


    def upsert_actual(
        self,
        *,
        tenant: str,
        month: str,
        job_name: str,
        build_id: str,
        actual_cost_usd: Optional[float],
        actual_runtime_seconds: Optional[float],
        finished_ts: Optional[str],
    ) -> None:
        entry_id = f"{tenant}:{build_id}:{job_name}"

        obj = self._load()
        entries = obj.get("entries", [])
        if not isinstance(entries, list):
            entries = []

        for i, e in enumerate(entries):
            if not isinstance(e, dict):
                continue
            if e.get("entry_id") != entry_id:
                continue
            if actual_cost_usd is not None:
                e["actual_cost_usd"] = float(actual_cost_usd)
            if actual_runtime_seconds is not None:
                e["actual_runtime_seconds"] = float(actual_runtime_seconds)
            if finished_ts is not None:
                e["finished_ts"] = finished_ts
            entries[i] = e
            obj["entries"] = entries
            self._save(obj)
            return

        # If estimate entry missing, create a minimal entry with actuals (best-effort)
        entries.append(
            {
                "entry_id": entry_id,
                "tenant": tenant,
                "month": month,
                "job_name": job_name,
                "build_id": build_id,
                "estimated_cost_usd": 0.0,
                "ts": _utc_now_iso(),
                "actual_cost_usd": float(actual_cost_usd) if actual_cost_usd is not None else None,
                "actual_runtime_seconds": float(actual_runtime_seconds) if actual_runtime_seconds is not None else None,
                "finished_ts": finished_ts,
            }
        )
        obj["entries"] = entries
        self._save(obj)

    def spent_actual_usd(self, *, tenant: str, month: str) -> float:
        obj = self._load()
        entries = obj.get("entries", [])
        if not isinstance(entries, list):
            return 0.0
        total = 0.0
        for e in entries:
            if not isinstance(e, dict):
                continue
            if e.get("tenant") != tenant:
                continue
            if e.get("month") != month:
                continue
            v = e.get("actual_cost_usd")
            if isinstance(v, (int, float)):
                total += float(v)
        return total

    def entries_count(self, *, tenant: str, month: str) -> int:
        obj = self._load()
        entries = obj.get("entries", [])
        if not isinstance(entries, list):
            return 0
        n = 0
        for e in entries:
            if not isinstance(e, dict):
                continue
            if e.get("tenant") != tenant:
                continue
            if e.get("month") != month:
                continue
            n += 1
        return n

    def spent_usd(self, *, tenant: str, month: str) -> float:
        obj = self._load()
        entries = obj.get("entries", [])
        if not isinstance(entries, list):
            return 0.0

        total = 0.0
        for e in entries:
            if not isinstance(e, dict):
                continue
            if e.get("tenant") != tenant:
                continue
            if e.get("month") != month:
                continue
            v = e.get("estimated_cost_usd")
            if isinstance(v, (int, float)):
                total += float(v)
        return total
