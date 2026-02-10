from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.core.git_ops.repo_manager import (
    read_baseline,
    read_upstream,
    get_ref,
    diff_name_status_scoped,
    show_file_at_ref,
)


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
    p = audit_log_path(repo_dir)
    line = json.dumps(event, ensure_ascii=False)
    p.write_text((p.read_text(encoding="utf-8") if p.exists() else "") + line + "\n", encoding="utf-8")


def parse_paths(paths: str) -> List[str]:
    include = [p.strip() for p in (paths or "").split(",") if p.strip()]
    # Always exclude metadata from planning/apply
    include = [p for p in include if p != ".copilot" and not p.startswith(".copilot")]
    return include


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

    # Status-driven fast path (most important correctness fix)
    if status == "A":
        return {
            "hashes": {"baseline": base_h, "upstream": up_h, "workspace": ws_h},
            "classification": "manual",
            "reason": "workspace_only_file",
        }

    if status == "D":
        # File exists in upstream but missing in workspace
        return {
            "hashes": {"baseline": base_h, "upstream": up_h, "workspace": ws_h},
            "classification": "safe_auto",
            "reason": "missing_in_workspace_restore_from_upstream",
        }

    # For M (or anything else), do baseline-aware change detection
    # If upstream file content is missing, we can't safely apply it.
    if up_txt is None:
        return {
            "hashes": {"baseline": base_h, "upstream": up_h, "workspace": ws_h},
            "classification": "manual",
            "reason": "upstream_missing_content",
        }

    # baseline-aware logic
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


def build_sync_plan(
    repo_dir: Path,
    scopes: List[str],
    max_diff_chars: int = 200000,
) -> Dict[str, Any]:
    """
    Build a deterministic plan for upstream -> workspace sync.
    Uses:
      - upstream ref from .copilot/upstream.json
      - baseline from .copilot/baseline.json (if present)
      - workspace HEAD
    """
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

    # Name/status diff tells us which files differ between upstream and workspace *in scopes*
    name_status = diff_name_status_scoped(repo_dir, upstream_ref, ws_ref, paths=scopes)

    items: List[Dict[str, Any]] = []
    for rec in name_status:
        path = rec["path"]
        status = rec["status"]  # A/M/D

        # compute baseline-based classification
        cls = classify_file(repo_dir, baseline_ref, upstream_ref, ws_ref, path, status)

        # Treat deletes/creates explicitly but keep classification consistent
        # If upstream has file and workspace doesn't -> safe_auto
        # If upstream doesn't and workspace has -> manual (don't delete user work) unless both unchanged vs baseline
        # classification already captures change vs baseline
        item = {
            "path": path,
            "scope": _scope_for_path(path, scopes),
            "status": status,
            **cls,
        }
        # Basic diff preview is optional in v1; keep plan lightweight and deterministic.
        # (UI can call /repo/upstream/diff if needed)
        items.append(item)

    summary = {
        "files_total": len(items),
        "safe_auto": sum(1 for i in items if i["classification"] == "safe_auto"),
        "manual": sum(1 for i in items if i["classification"] == "manual"),
        "conflicts": sum(1 for i in items if i["classification"] == "conflict"),
        "unchanged": sum(1 for i in items if i["classification"] == "unchanged"),
    }

    plan_id = str(uuid4())
    plan = {
        "plan_id": plan_id,
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
        "baseline": {"ref": baseline_ref},
        "scopes": scopes,
        "summary": summary,
        "items": items,
    }

    # persist plan
    plan_path(repo_dir, plan_id).write_text(json.dumps(plan, indent=2), encoding="utf-8")

    # audit
    write_audit(repo_dir, {"ts": now_utc_iso(), "event": "sync_plan", "plan_id": plan_id, "scopes": scopes, "summary": summary})
    return plan


def load_plan(repo_dir: Path, plan_id: str) -> Dict[str, Any]:
    p = plan_path(repo_dir, plan_id)
    if not p.exists():
        raise FileNotFoundError(f"Plan not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def apply_plan(repo_dir: Path, plan_id: str, apply_safe_auto: bool = True) -> Dict[str, Any]:
    """
    Apply only safe_auto items from a plan:
      - For A/M in upstream: write upstream version into working tree
      - For D in upstream: delete file from working tree (only when classified safe_auto)
    Then commit a single "copilot: sync apply" commit.
    """
    plan = load_plan(repo_dir, plan_id)
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
        #   A => workspace-only => should never be safe_auto; but keep guard
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

    write_audit(repo_dir, {"ts": now_utc_iso(), "event": "sync_apply", "plan_id": plan_id, "result": {"applied": len(applied), "skipped": len(skipped)}, "commit": commit_sha})
    return result


def _scope_for_path(path: str, scopes: List[str]) -> str:
    for s in scopes:
        if path == s or path.startswith(f"{s}/"):
            return s
    return "other"
