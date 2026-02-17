from __future__ import annotations

import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.core.git_ops.repo_manager import (
    diff_name_status_scoped,
    get_ref,
    read_baseline,
    read_upstream,
    show_file_at_ref,
)

# --------------------------------------------------------------------------------------
# Small, local git helpers (kept here to avoid expanding repo_manager surface area in MVP)
# --------------------------------------------------------------------------------------


def _run_git(repo_dir: Path, args: List[str]) -> tuple[int, str, str]:
    import os

    p = subprocess.run(
        ["git", "--no-pager", *args],
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "GIT_PAGER": "cat", "PAGER": "cat"},
    )
    return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()


def merge_base(repo_dir: Path, a_ref: str, b_ref: str) -> Optional[str]:
    """
    Returns merge-base SHA if histories are related, else None.
    """
    rc, out, _ = _run_git(repo_dir, ["merge-base", a_ref, b_ref])
    if rc != 0 or not out:
        return None
    return out


def is_ancestor(repo_dir: Path, ancestor_ref: str, descendant_ref: str) -> bool:
    """
    True if ancestor_ref is an ancestor of descendant_ref, else False.
    """
    rc, _, _ = _run_git(repo_dir, ["merge-base", "--is-ancestor", ancestor_ref, descendant_ref])
    return rc == 0


# --------------------------------------------------------------------------------------
# Stage 5: Drift Risk Engine (additive metadata only; no behavior change)
# --------------------------------------------------------------------------------------


def compute_sync_risk(
    *,
    topology_kind: str,
    histories_related: bool,
    baseline_ref: Optional[str],
    baseline_valid: bool,
    baseline_is_ancestor_of_ws: bool,
    baseline_is_ancestor_of_up: bool,
) -> Dict[str, Any]:
    """Compute deterministic drift risk for a sync plan.

    This is additive metadata only; it must NOT change planning/apply behavior.
    """
    base_scores = {
        "workspace_behind_linear": 1,
        "workspace_ahead_linear": 2,
        "diverged": 6,
        "unrelated_histories": 10,
    }

    score = base_scores.get(topology_kind, 5)
    reasons: List[str] = []

    if not histories_related:
        reasons.append("unrelated_histories")
        score = max(score, 10)

    if baseline_ref:
        if not baseline_valid:
            reasons.append("baseline_invalid")
            score = max(score, 8)
        if not baseline_is_ancestor_of_ws:
            reasons.append("baseline_not_ancestor_of_workspace")
            score = max(score, 8)
        if not baseline_is_ancestor_of_up:
            reasons.append("baseline_not_ancestor_of_upstream")
            score = max(score, 7)
    else:
        reasons.append("no_baseline")
        score = max(score, 3)

    if topology_kind == "diverged":
        reasons.append("diverged_histories")
        score = max(score, 6)

    score = max(0, min(10, int(score)))

    if score <= 2:
        severity = "LOW"
    elif score <= 5:
        severity = "MEDIUM"
    elif score <= 7:
        severity = "HIGH"
    elif score <= 9:
        severity = "CRITICAL"
    else:
        severity = "BLOCKING"

    auto_apply_allowed = (
        severity == "LOW"
        and histories_related
        and topology_kind in ("workspace_ahead_linear", "workspace_behind_linear")
        and (not baseline_ref or baseline_is_ancestor_of_ws)
        and (not baseline_ref or baseline_is_ancestor_of_up)
    )

    return {
        "score": score,
        "severity": severity,
        "reasons": sorted(set(reasons)),
        "auto_apply_allowed": auto_apply_allowed,
    }


# --------------------------------------------------------------------------------------
# Utils
# --------------------------------------------------------------------------------------


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_text(txt: Optional[str]) -> Optional[str]:
    if txt is None:
        return None
    return hashlib.sha256(txt.encode("utf-8", errors="replace")).hexdigest()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def plan_root(repo_dir: Path) -> Path:
    return repo_dir / ".copilot" / "plans"


def plan_path(repo_dir: Path, plan_id: str) -> Path:
    return plan_root(repo_dir) / f"{plan_id}.json"


def audit_log_path(repo_dir: Path) -> Path:
    return repo_dir / ".copilot" / "audit.log"


def write_audit(repo_dir: Path, event: Dict[str, Any]) -> None:
    audit_log_path(repo_dir).parent.mkdir(parents=True, exist_ok=True)
    with audit_log_path(repo_dir).open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def parse_paths(paths: str) -> List[str]:
    p = [x.strip() for x in (paths or "").split(",") if x.strip()]
    if not p:
        return ["jobs", "dags", "configs"]
    return p


def _scope_for_path(rel_path: str, scopes: List[str]) -> str:
    rel = rel_path.replace("\\", "/")
    for s in scopes:
        s2 = s.strip().strip("/")
        if not s2:
            continue
        if rel == s2 or rel.startswith(s2 + "/"):
            return s2
    return scopes[0] if scopes else "jobs"


# --------------------------------------------------------------------------------------
# Plan
# --------------------------------------------------------------------------------------


def build_sync_plan(
    repo_dir: Path,
    scopes: List[str],
    max_diff_chars: int = 200000,
) -> Dict[str, Any]:
    """
    Build a deterministic plan for upstream -> workspace sync.
    Uses:
      - upstream ref from .copilot/upstream.json (requires last_fetch_at)
      - baseline from .copilot/baseline.json (if present)
      - workspace HEAD
      - merge-base intelligence for topology + safe fallbacks
    """
    _ = max_diff_chars  # reserved for future diff-preview limiting
    start_total = time.perf_counter()

    cfg = read_upstream(repo_dir)
    if not cfg or not cfg.get("last_fetch_at"):
        raise ValueError("Upstream not connected/fetched. Call /repo/upstream/connect and /repo/upstream/fetch first.")

    remote = cfg.get("remote", "upstream")
    branch = cfg.get("branch", "main")
    upstream_ref = cfg.get("remote_ref", f"{remote}/{branch}")

    ws_ref = "HEAD"
    ws_head = get_ref(repo_dir, ws_ref)
    upstream_head = get_ref(repo_dir, upstream_ref)

    baseline_ref = read_baseline(repo_dir)

    # --- topology ---
    mb_wu = merge_base(repo_dir, ws_ref, upstream_ref)
    histories_related = mb_wu is not None

    if not histories_related:
        topology_kind = "unrelated_histories"
    elif is_ancestor(repo_dir, upstream_ref, ws_ref):
        topology_kind = "workspace_ahead_linear"
    elif is_ancestor(repo_dir, ws_ref, upstream_ref):
        topology_kind = "workspace_behind_linear"
    else:
        topology_kind = "diverged"

    baseline_is_ancestor_of_ws = False
    baseline_is_ancestor_of_up = False
    baseline_valid = False
    if baseline_ref:
        baseline_valid = True
        try:
            baseline_is_ancestor_of_ws = is_ancestor(repo_dir, baseline_ref, ws_ref)
        except Exception:
            baseline_is_ancestor_of_ws = False
        try:
            baseline_is_ancestor_of_up = is_ancestor(repo_dir, baseline_ref, upstream_ref)
        except Exception:
            baseline_is_ancestor_of_up = False

    mb_bu = merge_base(repo_dir, baseline_ref, upstream_ref) if baseline_ref else None
    mb_bw = merge_base(repo_dir, baseline_ref, ws_ref) if baseline_ref else None

    # Effective baseline for planning:
    # - prefer baseline if it is an ancestor of workspace
    # - else fall back to merge-base(WS,UP) when histories are related
    # - else fall back to upstream_head (forces conservative hashing, no auto-apply anyway)
    if baseline_ref and baseline_is_ancestor_of_ws:
        baseline_ref_effective = baseline_ref
    elif mb_wu:
        baseline_ref_effective = mb_wu
    else:
        baseline_ref_effective = upstream_head

    # Recommended action is advisory only.
    if not histories_related:
        recommended_action = "reset_or_rebaseline_required"
    elif topology_kind == "diverged":
        recommended_action = "manual_resolution_required"
    elif topology_kind == "workspace_behind_linear":
        recommended_action = "safe_auto_apply_possible"
    elif topology_kind == "workspace_ahead_linear":
        recommended_action = "workspace_ahead_review_then_apply"
    else:
        recommended_action = "manual_review"

    # --- diff ---
    start_diff = time.perf_counter()
    name_status = diff_name_status_scoped(repo_dir, upstream_ref, ws_ref, paths=scopes)
    end_diff = time.perf_counter()

    # --- classify ---
    start_classify = time.perf_counter()
    items: List[Dict[str, Any]] = []

    for rec in name_status:
        path = rec["path"]
        status = rec["status"]

        if not histories_related:
            base_txt = show_file_at_ref(repo_dir, baseline_ref, path) if baseline_ref else None
            up_txt = show_file_at_ref(repo_dir, upstream_ref, path)
            ws_txt = show_file_at_ref(repo_dir, ws_ref, path)

            items.append(
                {
                    "path": path,
                    "scope": _scope_for_path(path, scopes),
                    "status": status,
                    "hashes": {
                        "baseline": sha256_text(base_txt),
                        "upstream": sha256_text(up_txt),
                        "workspace": sha256_text(ws_txt),
                    },
                    "apply_mode": "manual",
                    "reason": "unrelated_histories",
                }
            )
            continue

        base_txt = show_file_at_ref(repo_dir, baseline_ref_effective, path) if baseline_ref_effective else None
        up_txt = show_file_at_ref(repo_dir, upstream_ref, path)
        ws_txt = show_file_at_ref(repo_dir, ws_ref, path)

        h_base = sha256_text(base_txt)
        h_up = sha256_text(up_txt)
        h_ws = sha256_text(ws_txt)

        # Conservative modes:
        # - If diverged, force manual (even if per-file hashes suggest a safe overwrite).
        # - Otherwise allow safe_auto only when workspace matches baseline and upstream changed.
        if topology_kind == "diverged":
            apply_mode = "manual"
            reason = "diverged"
        else:
            if h_ws == h_base and h_up != h_base:
                apply_mode = "safe_auto"
                reason = "workspace_clean_upstream_changed"
            else:
                apply_mode = "manual"
                reason = "requires_manual_review"

        items.append(
            {
                "path": path,
                "scope": _scope_for_path(path, scopes),
                "status": status,
                "hashes": {"baseline": h_base, "upstream": h_up, "workspace": h_ws},
                "apply_mode": apply_mode,
                "reason": reason,
            }
        )

    end_classify = time.perf_counter()

    safe_auto = [x for x in items if x.get("apply_mode") == "safe_auto"]
    manual = [x for x in items if x.get("apply_mode") != "safe_auto"]

    summary = {
        "total_items": len(items),
        "safe_auto_items": len(safe_auto),
        "manual_items": len(manual),
        "recommended_action": recommended_action,
    }

    plan_id = uuid4().hex

    plan = {
        "plan_id": plan_id,
        "baseline_ref": baseline_ref_effective,  # what we actually planned against
        "upstream_ref": upstream_ref,
        "created_at": now_utc_iso(),
        "upstream": {"head": upstream_head},
        "workspace": {"head": ws_head},
        "baseline": {"ref": baseline_ref},  # raw baseline as stored
        "scopes": scopes,
        "summary": summary,
        "items": items,
        "topology": {
            "kind": topology_kind,
            "histories_related": histories_related,
            "merge_base_ws_up": mb_wu,
            "merge_base_base_up": mb_bu,
            "merge_base_base_ws": mb_bw,
            "baseline_valid": baseline_valid,
            "baseline_is_ancestor_of_ws": baseline_is_ancestor_of_ws,
            "baseline_is_ancestor_of_up": baseline_is_ancestor_of_up,
            "recommended_action": recommended_action,
        },
        "risk": compute_sync_risk(
            topology_kind=topology_kind,
            histories_related=histories_related,
            baseline_ref=baseline_ref,
            baseline_valid=baseline_valid,
            baseline_is_ancestor_of_ws=baseline_is_ancestor_of_ws,
            baseline_is_ancestor_of_up=baseline_is_ancestor_of_up,
        ),
        "profiling": {
            "total_seconds": round(time.perf_counter() - start_total, 6),
            "diff_seconds": round(end_diff - start_diff, 6),
            "classify_seconds": round(end_classify - start_classify, 6),
        },
    }

    plan_root(repo_dir).mkdir(parents=True, exist_ok=True)
    plan_file = plan_path(repo_dir, plan_id)
    plan_file.write_text(json.dumps(plan, indent=2, sort_keys=True), encoding="utf-8")

    write_audit(
        repo_dir,
        {
            "ts": now_utc_iso(),
            "action": "sync.plan",
            "plan_id": plan_id,
            "upstream_ref": upstream_ref,
            "ws_head": ws_head,
            "upstream_head": upstream_head,
            "baseline_ref_effective": baseline_ref_effective,
            "topology_kind": topology_kind,
            "summary": summary,
        },
    )

    return plan


# --------------------------------------------------------------------------------------
# Load / Apply
# --------------------------------------------------------------------------------------


def load_plan(repo_dir: Path, plan_id: str) -> Dict[str, Any]:
    p = plan_path(repo_dir, plan_id)
    if not p.exists():
        raise FileNotFoundError(f"Plan not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def apply_plan(repo_dir: Path, plan_id: str, apply_safe_auto: bool = True) -> Dict[str, Any]:
    plan = load_plan(repo_dir, plan_id)

    ws_ref = "HEAD"
    upstream_ref = plan.get("upstream_ref")
    if not upstream_ref:
        raise ValueError("Plan missing upstream_ref")

    # stale plan detection
    current_ws_head = get_ref(repo_dir, ws_ref)
    current_up_head = get_ref(repo_dir, upstream_ref)

    if plan.get("workspace", {}).get("head") != current_ws_head:
        raise ValueError("Stale plan: workspace HEAD changed since plan creation.")
    if plan.get("upstream", {}).get("head") != current_up_head:
        raise ValueError("Stale plan: upstream HEAD changed since plan creation.")

    items = plan.get("items", [])
    applied: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []

    for item in items:
        mode = item.get("apply_mode")
        path = item.get("path")

        if mode == "safe_auto" and apply_safe_auto:
            # overwrite workspace with upstream version
            up_txt = show_file_at_ref(repo_dir, upstream_ref, path)
            if up_txt is None:
                skipped.append({**item, "skip_reason": "missing_upstream_content"})
                continue

            out_path = repo_dir / path
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(up_txt, encoding="utf-8")

            applied.append({**item, "applied": True})
        else:
            skipped.append({**item, "applied": False})

    write_audit(
        repo_dir,
        {
            "ts": now_utc_iso(),
            "action": "sync.apply",
            "plan_id": plan_id,
            "applied_count": len(applied),
            "skipped_count": len(skipped),
            "apply_safe_auto": bool(apply_safe_auto),
        },
    )

    return {
        "plan_id": plan_id,
        "applied_count": len(applied),
        "skipped_count": len(skipped),
        "applied": applied,
        "skipped": skipped,
    }
