# app/core/sync/sync_engine.py

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
# Utils
# --------------------------------------------------------------------------------------


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_text(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    return hashlib.sha256(s.encode("utf-8", errors="replace")).hexdigest()


def ensure_copilot_dirs(repo_dir: Path) -> Path:
    copilot_dir = repo_dir / ".copilot"
    copilot_dir.mkdir(parents=True, exist_ok=True)
    (copilot_dir / "plans").mkdir(parents=True, exist_ok=True)
    return copilot_dir


def plan_path(repo_dir: Path, plan_id: str) -> Path:
    return ensure_copilot_dirs(repo_dir) / "plans" / f"{plan_id}.json"


def audit_log_path(repo_dir: Path) -> Path:
    return ensure_copilot_dirs(repo_dir) / "audit.log"


def write_audit(repo_dir: Path, event: Dict[str, Any]) -> None:
    """
    Append one JSON line into .copilot/audit.log
    """
    p = audit_log_path(repo_dir)
    line = json.dumps(event, ensure_ascii=False)
    with p.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def parse_paths(paths: str) -> List[str]:
    include = [p.strip() for p in (paths or "").split(",") if p.strip()]
    include = [p for p in include if p != ".copilot" and not p.startswith(".copilot")]
    return include


def _scope_for_path(path: str, scopes: List[str]) -> str:
    for s in scopes:
        if path == s or path.startswith(f"{s}/"):
            return s
    return "other"


# --------------------------------------------------------------------------------------
# Classification
# --------------------------------------------------------------------------------------


def classify_file(
    repo_dir: Path,
    baseline_ref: Optional[str],
    upstream_ref: str,
    ws_ref: str,
    path: str,
    status: str,
) -> Dict[str, Any]:
    """
    Direction-aware classification for upstream -> workspace, where name-status comes from:
      git diff --name-status upstream_ref..HEAD

    Status meaning in that diff:
      A: file exists only in workspace (added in HEAD)
      D: file exists only in upstream (deleted in workspace)
      M: file exists in both but differs

    Rules (MVP safe):
      - A => manual (workspace-only file; never delete automatically)
      - D => safe_auto (restore from upstream into workspace)
      - M => baseline-aware:
            if workspace changed since baseline AND upstream differs => conflict
            if only upstream differs vs baseline => safe_auto
            if only workspace differs vs baseline => manual
    """
    base_txt = show_file_at_ref(repo_dir, baseline_ref, path) if baseline_ref else None
    up_txt = show_file_at_ref(repo_dir, upstream_ref, path)
    ws_txt = show_file_at_ref(repo_dir, ws_ref, path)

    base_h = sha256_text(base_txt)
    up_h = sha256_text(up_txt)
    ws_h = sha256_text(ws_txt)

    if status == "A":
        return {
            "hashes": {"baseline": base_h, "upstream": up_h, "workspace": ws_h},
            "classification": "manual",
            "reason": "workspace_only_file",
        }

    if status == "D":
        return {
            "hashes": {"baseline": base_h, "upstream": up_h, "workspace": ws_h},
            "classification": "safe_auto",
            "reason": "missing_in_workspace_restore_from_upstream",
        }

    # M (or anything else): baseline-aware
    if up_txt is None:
        return {
            "hashes": {"baseline": base_h, "upstream": up_h, "workspace": ws_h},
            "classification": "manual",
            "reason": "upstream_missing_content",
        }

    up_changed = (up_h != base_h)
    ws_changed = (ws_h != base_h)

    if up_changed and not ws_changed:
        classification = "safe_auto"
        reason = "upstream_changed_only"
    elif ws_changed and not up_changed:
        classification = "manual"
        reason = "workspace_changed_only"
    elif up_changed and ws_changed:
        classification = "conflict"
        reason = "both_changed_since_baseline"
    else:
        classification = "unchanged"
        reason = "no_change"

    return {
        "hashes": {"baseline": base_h, "upstream": up_h, "workspace": ws_h},
        "classification": classification,
        "reason": reason,
    }


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
            # Unrelated histories: never auto-apply. Provide hashes for UX/debug.
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
                    "classification": "manual",
                    "reason": "unrelated_histories_requires_reset_or_rebaseline",
                }
            )
            continue

        cls = classify_file(repo_dir, baseline_ref_effective, upstream_ref, ws_ref, path, status)
        items.append(
            {
                "path": path,
                "scope": _scope_for_path(path, scopes),
                "status": status,
                **cls,
            }
        )

    end_classify = time.perf_counter()

    summary = {
        "files_total": len(items),
        "safe_auto": sum(1 for i in items if i["classification"] == "safe_auto"),
        "manual": sum(1 for i in items if i["classification"] == "manual"),
        "conflicts": sum(1 for i in items if i["classification"] == "conflict"),
        "unchanged": sum(1 for i in items if i["classification"] == "unchanged"),
    }

    recommended_action = "sync_ok"
    if not histories_related:
        recommended_action = "reset_or_rebaseline_required"
    elif baseline_ref and not baseline_is_ancestor_of_ws:
        recommended_action = "rebaseline_recommended"
    elif baseline_ref and baseline_is_ancestor_of_ws and not baseline_is_ancestor_of_up:
        recommended_action = "baseline_not_in_upstream_use_merge_base"

    plan_id = str(uuid4())

    plan = {
        "plan_id": plan_id,
        "baseline_ref": baseline_ref_effective,  # what we actually used for classification
        "created_at": now_utc_iso(),
        "upstream": {
            "remote": cfg.get("remote"),
            "repo_url": cfg.get("repo_url"),
            "branch": cfg.get("branch"),
            "ref": upstream_ref,
            "head": upstream_head,
            "last_fetch_at": cfg.get("last_fetch_at"),
        },
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
        "profiling": {
            "total_seconds": round(time.perf_counter() - start_total, 6),
            "diff_seconds": round(end_diff - start_diff, 6),
            "classification_seconds": round(end_classify - start_classify, 6),
            "files_evaluated": len(items),
        },
    }

    plan_path(repo_dir, plan_id).write_text(json.dumps(plan, indent=2), encoding="utf-8")

    write_audit(
        repo_dir,
        {
            "ts": now_utc_iso(),
            "event": "sync_plan",
            "plan_id": plan_id,
            "scopes": scopes,
            "summary": summary,
            "topology": plan["topology"],
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
    """
    Apply only safe_auto items from a plan:
      - For D or M in upstream_ref..HEAD diff: write upstream version into working tree
      - Never delete workspace-only files automatically
    Then commit a single "copilot: sync apply" commit.
    """
    plan = load_plan(repo_dir, plan_id)

    # Hard guard: if histories are unrelated, do NOT apply anything.
    topo = plan.get("topology") or {}
    if topo.get("histories_related") is False:
        raise ValueError("Cannot apply plan: unrelated histories. Use /repo/upstream/switch?mode=reset or mode=rebaseline.")

    upstream_ref = plan["upstream"]["ref"]
    planned_upstream_head = plan["upstream"]["head"]
    current_upstream_head = get_ref(repo_dir, upstream_ref)
    if planned_upstream_head != current_upstream_head:
        raise ValueError(
            f"Plan is stale: upstream head changed from {planned_upstream_head} to {current_upstream_head}. Re-run /sync/plan."
        )

    applied: List[str] = []
    skipped: List[Dict[str, str]] = []

    for item in plan["items"]:
        path = item["path"]
        classification = item["classification"]
        status = item["status"]

        if classification != "safe_auto":
            skipped.append({"path": path, "reason": item.get("reason", classification)})
            continue

        if not apply_safe_auto:
            skipped.append({"path": path, "reason": "safe_auto_not_applied"})
            continue

        abs_path = repo_dir / path
        abs_path.parent.mkdir(parents=True, exist_ok=True)

        # For upstream_ref..HEAD diff:
        #   D => missing in workspace, present in upstream => RESTORE from upstream
        #   M => differs => WRITE upstream version
        if status in ("D", "M"):
            content = show_file_at_ref(repo_dir, upstream_ref, path)
            if content is None:
                skipped.append({"path": path, "reason": "upstream_missing_content"})
                continue
            abs_path.write_text(content, encoding="utf-8", errors="replace")
            applied.append(path)
        else:
            skipped.append({"path": path, "reason": f"unsupported_status_for_apply:{status}"})

    # commit if something changed
    from app.core.git_ops.repo_manager import commit_all  # local import to avoid circulars

    commit_sha = None
    if applied:
        commit_sha = commit_all(repo_dir, f"copilot: sync apply ({plan_id})")

    result = {
        "plan_id": plan_id,
        "applied_count": len(applied),
        "applied": applied,
        "skipped_count": len(skipped),
        "skipped": skipped,
        "commit": commit_sha,
    }

    write_audit(
        repo_dir,
        {
            "ts": now_utc_iso(),
            "event": "sync_apply",
            "plan_id": plan_id,
            "result": {"applied": len(applied), "skipped": len(skipped)},
            "commit": commit_sha,
        },
    )

    return result
