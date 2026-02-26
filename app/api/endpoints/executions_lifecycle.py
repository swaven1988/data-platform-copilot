from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.core.auth.rbac import require_role
from app.core.execution.lifecycle import ExecutionStore, ExecutionRecord, now_ts, request_cancel, reconcile_stale_runs

router = APIRouter()

# process-wide store (matches existing patterns in repo; swap later)
STORE = ExecutionStore()


class CreateRunReq(BaseModel):
    run_id: str


@router.post("/executions/create", dependencies=[Depends(require_role("admin"))])
def create_run(req: CreateRunReq):
    rec = ExecutionRecord(
        run_id=req.run_id,
        status="RUNNING",
        created_ts=now_ts(),
        updated_ts=now_ts(),
        cancel_requested=False,
        terminal_reason=None,
    )
    STORE.put(rec)
    return {"run_id": rec.run_id, "status": rec.status}


@router.post("/executions/{run_id}/cancel", dependencies=[Depends(require_role("admin"))])
def cancel_run(run_id: str):
    try:
        rec = request_cancel(STORE, run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="run_not_found")
    return {"run_id": rec.run_id, "status": rec.status, "cancel_requested": rec.cancel_requested}


@router.post("/executions/reconcile", dependencies=[Depends(require_role("admin"))])
def reconcile(stale_after_seconds: int = 60):
    n = reconcile_stale_runs(STORE, stale_after_seconds=stale_after_seconds)
    return {"reconciled": n}