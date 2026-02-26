# app/core/git_ops/repo_manager.py

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List
from datetime import datetime, timezone


# ---------------------------------------------------------------------
# Core git runner (deterministic, no debug prints, strict semantics)
# ---------------------------------------------------------------------

def _run_git(repo_path: Path, args: list[str]) -> Tuple[int, str, str]:
    import os
    p = subprocess.run(
        ["git", "--no-pager", *args],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "GIT_PAGER": "cat", "PAGER": "cat"},
    )
    return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()


def ensure_repo(repo_path: Path) -> None:
    repo_path.mkdir(parents=True, exist_ok=True)
    if (repo_path / ".git").exists():
        return
    rc, out, err = _run_git(repo_path, ["init"])
    if rc != 0:
        raise RuntimeError(f"git init failed: {err or out}")


# ---------------------------------------------------------------------
# Basic state
# ---------------------------------------------------------------------

def git_status(repo_path: Path) -> Dict[str, Any]:
    rc1, branch, _ = _run_git(repo_path, ["rev-parse", "--abbrev-ref", "HEAD"])
    if rc1 != 0:
        branch = "(unknown)"

    rc2, status, err2 = _run_git(repo_path, ["status", "--porcelain"])
    if rc2 != 0:
        raise RuntimeError(f"git status failed: {err2}")

    return {
        "branch": branch,
        "dirty": bool(status),
        "porcelain": status.splitlines() if status else [],
    }


def is_dirty(repo_path: Path) -> bool:
    return git_status(repo_path)["dirty"]


def get_ref(repo_path: Path, ref: str) -> str:
    rc, out, err = _run_git(repo_path, ["rev-parse", ref])
    if rc != 0:
        raise RuntimeError(f"git rev-parse {ref} failed: {err or out}")
    return out


def commit_all(repo_path: Path, message: str) -> str:
    rc1, _, err1 = _run_git(repo_path, ["add", "-A"])
    if rc1 != 0:
        raise RuntimeError(f"git add failed: {err1}")

    rc2, _, err2 = _run_git(repo_path, ["commit", "-m", message])
    if rc2 != 0:
        rc3, head, err3 = _run_git(repo_path, ["rev-parse", "HEAD"])
        if rc3 == 0:
            return head
        raise RuntimeError(f"git commit failed: {err2 or err3}")

    return get_ref(repo_path, "HEAD")


# ---------------------------------------------------------------------
# Merge-base / ancestry (merge-base intelligence)
# ---------------------------------------------------------------------

def merge_base(repo_path: Path, left_ref: str, right_ref: str) -> Optional[str]:
    rc, out, err = _run_git(repo_path, ["merge-base", left_ref, right_ref])
    if rc != 0:
        return None
    return out.strip() or None


def is_ancestor(repo_path: Path, ancestor_ref: str, descendant_ref: str) -> bool:
    rc, _, _ = _run_git(repo_path, ["merge-base", "--is-ancestor", ancestor_ref, descendant_ref])
    return rc == 0

# ---------------------------------------------------------------------
# Diff (correct empty-diff semantics)
# ---------------------------------------------------------------------

def diff(repo_path: Path, base_ref: str, head_ref: str = "HEAD") -> str:
    rc, out, err = _run_git(repo_path, ["diff", f"{base_ref}..{head_ref}"])
    if rc == 0:
        return out or ""
    raise RuntimeError(f"git diff failed: {err or out}")


def diff_scoped(
    repo_path: Path,
    base_ref: str,
    head_ref: str = "HEAD",
    paths: Optional[List[str]] = None,
) -> str:
    args = ["diff", f"{base_ref}..{head_ref}"]
    if paths:
        args += ["--", *paths]
    rc, out, err = _run_git(repo_path, args)
    if rc == 0:
        return out or ""
    raise RuntimeError(f"git diff (scoped) failed: {err or out}")


def diff_name_only_scoped(
    repo_path: Path,
    from_ref: str,
    to_ref: str,
    paths: Optional[List[str]] = None,
) -> List[str]:
    args = ["diff", "--name-only", f"{from_ref}..{to_ref}"]
    if paths:
        args += ["--", *paths]
    rc, out, err = _run_git(repo_path, args)
    if rc != 0:
        raise RuntimeError(f"git diff --name-only failed: {err}")
    return out.splitlines() if out else []


def diff_name_status_scoped(
    repo_path: Path,
    from_ref: str,
    to_ref: str,
    paths: Optional[List[str]] = None,
) -> List[Dict[str, str]]:
    args = ["diff", "--name-status", f"{from_ref}..{to_ref}"]
    if paths:
        args += ["--", *paths]
    rc, out, err = _run_git(repo_path, args)
    if rc != 0:
        raise RuntimeError(f"git diff --name-status failed: {err}")

    items: List[Dict[str, str]] = []
    for line in (out.splitlines() if out else []):
        parts = line.split("\t", 1)
        if len(parts) == 2:
            items.append({"status": parts[0].strip(), "path": parts[1].strip()})
    return items


# ---------------------------------------------------------------------
# Baseline
# ---------------------------------------------------------------------

def read_baseline(repo_path: Path) -> Optional[str]:
    meta = repo_path / ".copilot" / "baseline.json"
    if not meta.exists():
        return None
    data = json.loads(meta.read_text(encoding="utf-8"))
    ref = data.get("baseline_commit")
    if not ref:
        return None
    get_ref(repo_path, ref)
    return ref


def write_baseline(repo_path: Path, baseline_commit: str) -> None:
    get_ref(repo_path, baseline_commit)
    meta_dir = repo_path / ".copilot"
    meta_dir.mkdir(parents=True, exist_ok=True)
    (meta_dir / "baseline.json").write_text(
        json.dumps({"baseline_commit": baseline_commit}, indent=2),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------
# Upstream
# ---------------------------------------------------------------------

def remote_exists(repo_path: Path, remote_name: str) -> bool:
    rc, out, err = _run_git(repo_path, ["remote"])
    if rc != 0:
        raise RuntimeError(err)
    return remote_name in (out.splitlines() if out else [])


def add_or_set_remote(repo_path: Path, remote_name: str, repo_url: str) -> None:
    if remote_exists(repo_path, remote_name):
        rc, _, err = _run_git(repo_path, ["remote", "set-url", remote_name, repo_url])
    else:
        rc, _, err = _run_git(repo_path, ["remote", "add", remote_name, repo_url])
    if rc != 0:
        raise RuntimeError(err)


def fetch_remote(repo_path: Path, remote_name: str) -> None:
    rc, _, err = _run_git(repo_path, ["fetch", "--prune", remote_name])
    if rc != 0:
        raise RuntimeError(f"git fetch failed: {err}")


def ahead_behind(repo_path: Path, left_ref: str, right_ref: str) -> Dict[str, int]:
    rc, out, err = _run_git(repo_path, ["rev-list", "--left-right", "--count", f"{left_ref}...{right_ref}"])
    if rc != 0:
        raise RuntimeError(err)
    parts = out.replace("\t", " ").split()
    return {
        "ahead": int(parts[0]) if len(parts) > 0 else 0,
        "behind": int(parts[1]) if len(parts) > 1 else 0,
    }


def read_upstream(repo_path: Path) -> Optional[Dict[str, Any]]:
    meta = repo_path / ".copilot" / "upstream.json"
    if not meta.exists():
        return None
    return json.loads(meta.read_text(encoding="utf-8"))


def write_upstream(repo_path: Path, data: Dict[str, Any]) -> None:
    meta_dir = repo_path / ".copilot"
    meta_dir.mkdir(parents=True, exist_ok=True)
    (meta_dir / "upstream.json").write_text(
        json.dumps(data, indent=2),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------

def hard_reset(repo_path: Path, ref: str, clean_untracked: bool = False) -> None:
    """
    Hard reset to ref. If clean_untracked is True, run a conservative clean that
    preserves .copilot/ metadata (upstream.json, baseline.json, audit.log, plans/).
    """
    get_ref(repo_path, ref)

    rc, _, err = _run_git(repo_path, ["reset", "--hard", ref])
    if rc != 0:
        raise RuntimeError(err)

    if clean_untracked:
        # Preserve Copilot metadata.
        # NOTE: git clean exclusions are matched against repo root paths.
        rc2, _, err2 = _run_git(
            repo_path,
            ["clean", "-fd", "-e", ".copilot", "-e", ".copilot/**"],
        )
        if rc2 != 0:
            raise RuntimeError(err2)


# ---------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------

def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def append_audit(repo_path: Path, event: str, payload: Dict[str, Any]) -> None:
    meta_dir = repo_path / ".copilot"
    meta_dir.mkdir(parents=True, exist_ok=True)
    audit = meta_dir / "audit.log"
    row = {"ts": now_utc_iso(), "event": event, **payload}
    with audit.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def show_file_at_ref(repo_path: Path, ref: Optional[str], file_path: str) -> Optional[str]:
    """
    Return file contents at a git ref using:
        git show <ref>:<path>

    Returns None if:
      - ref is None
      - file does not exist at that ref
    """
    if not ref:
        return None

    rc, out, _ = _run_git(repo_path, ["show", f"{ref}:{file_path}"])
    if rc != 0:
        return None
    return out
