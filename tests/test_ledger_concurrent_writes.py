"""Fix 8 test — concurrent writes to the ledger should not lose all data."""
from __future__ import annotations

import concurrent.futures
import sys
from pathlib import Path

from app.core.billing.ledger import LedgerStore, utc_month_key, _HAS_FCNTL


def test_concurrent_ledger_writes_no_corruption(tmp_path):
    """10 concurrent upsert_estimate calls — on POSIX all 10 must persist; on Windows at least 1."""
    ws = tmp_path / "ws"
    ws.mkdir()
    store = LedgerStore(workspace_dir=ws)
    month = utc_month_key()

    def write(i: int):
        return store.upsert_estimate(
            tenant="default",
            month=month,
            job_name=f"job_{i}",
            build_id=f"build_{i}",
            estimated_cost_usd=float(i),
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        futs = [pool.submit(write, i) for i in range(10)]
        results = [f.result() for f in concurrent.futures.as_completed(futs)]

    assert len(results) == 10

    obj = store._load()
    entries = obj.get("entries", [])
    job_names = {e["job_name"] for e in entries if isinstance(e, dict)}

    if _HAS_FCNTL:
        # POSIX: fcntl ensures all writes are serialised → all 10 must be present
        assert len(job_names) == 10, f"Expected 10 unique job entries, got: {job_names}"
    else:
        # Windows: no fcntl → concurrent writes may overwrite each other (documented limitation)
        # Verify at least 1 entry survived and there was no exception
        assert len(job_names) >= 1, "Ledger was completely corrupted — even single entry missing"
