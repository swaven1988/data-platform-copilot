from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List
from datetime import datetime, timezone


def _run_git(repo_path: Path, args: list[str]) -> Tuple[int, str, str]:
    """Run a git command in repo_path and return (rc, stdout, stderr)."""
    import os
    p = subprocess.run(
        ["git", "--no-pager", *args],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",   # <-- prevents UnicodeDecodeError
        env={**os.environ, "GIT_PAGER": "cat", "PAGER": "cat"},
    )
    return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()


def ensure_repo(repo_path: Path) -> None:
    repo_path.mkdir(parents=True, exist_ok=True)
    git_dir = repo_path / ".git"
    if git_dir.exists():
        return
    rc, out, err = _run_git(repo_path, ["init"])
    if rc != 0:
        raise RuntimeError(f"git init failed: {err or out}")


def git_status(repo_path: Path) -> Dict[str, Any]:
    rc1, branch, err1 = _run_git(repo_path, ["rev-parse", "--abbrev-ref", "HEAD"])
    if rc1 != 0:
        branch = "(no-branch)"
    rc2, status, err2 = _run_git(repo_path, ["status", "--porcelain"])
    if rc2 != 0:
        raise RuntimeError(f"git status failed: {err2 or status}")

    return {
        "branch": branch,
        "dirty": bool(status),
        "porcelain": status.splitlines() if status else [],
    }


def commit_all(repo_path: Path, message: str) -> str:
    # add all
    rc1, out1, err1 = _run_git(repo_path, ["add", "-A"])
    if rc1 != 0:
        raise RuntimeError(f"git add failed: {err1 or out1}")

    # commit (may fail if nothing to commit)
    rc2, out2, err2 = _run_git(repo_path, ["commit", "-m", message])
    if rc2 != 0:
        # if nothing to commit, return current HEAD
        rc3, head, err3 = _run_git(repo_path, ["rev-parse", "HEAD"])
        if rc3 == 0:
            return head
        raise RuntimeError(f"git commit failed: {err2 or out2}")

    # return new HEAD
    rc3, head, err3 = _run_git(repo_path, ["rev-parse", "HEAD"])
    if rc3 != 0:
        raise RuntimeError(f"git rev-parse failed: {err3 or head}")
    return head


def diff(repo_path: Path, base_ref: str, head_ref: str = "HEAD") -> str:
    # Preferred: rev-range form
    rc, out, err = _run_git(repo_path, ["diff", f"{base_ref}..{head_ref}"])
    if rc == 0 and out:
        print("[DEBUG diff]", base_ref, head_ref, "rc=", rc, "len(out)=", len(out or ""), "err=", err[:200])
        return out

    # Fallback: two-ref form (more reliable on some Windows setups)
    rc2, out2, err2 = _run_git(repo_path, ["diff", base_ref, head_ref])
    if rc2 == 0 and out2:
        print("[DEBUG diff fallback]", base_ref, head_ref, "rc2=", rc2, "len(out2)=", len(out2 or ""), "err2=", err2[:200])
        return out2

    # If still empty, return empty string (no diff) only when both calls succeeded with empty output
    if rc == 0 and (out == "" or out is None) and rc2 == 0 and (out2 == "" or out2 is None):
        return ""

    raise RuntimeError(f"git diff failed: {err2 or err or out2 or out}")


def diff_scoped(repo_path: Path, base_ref: str, head_ref: str = "HEAD", paths: Optional[List[str]] = None) -> str:
    """
    Scoped diff: git diff base..head -- <paths...>
    Uses the same Windows-safe encoding rules as _run_git.
    """
    paths = [p for p in (paths or []) if p]
    # Preferred: rev-range form
    args = ["diff", f"{base_ref}..{head_ref}"]
    if paths:
        args += ["--", *paths]
    rc, out, err = _run_git(repo_path, args)
    if rc == 0:
        return out or ""

    # Fallback: two-ref form
    args2 = ["diff", base_ref, head_ref]
    if paths:
        args2 += ["--", *paths]
    rc2, out2, err2 = _run_git(repo_path, args2)
    if rc2 == 0:
        return out2 or ""

    raise RuntimeError(f"git diff (scoped) failed: {err2 or err or out2 or out}")


def read_baseline(repo_path: Path) -> Optional[str]:
    meta = repo_path / ".copilot" / "baseline.json"
    if not meta.exists():
        return None
    try:
        data = json.loads(meta.read_text(encoding="utf-8"))
        return data.get("baseline_commit")
    except Exception:
        return None


def write_baseline(repo_path: Path, baseline_commit: str) -> None:
    meta_dir = repo_path / ".copilot"
    meta_dir.mkdir(parents=True, exist_ok=True)
    meta = meta_dir / "baseline.json"
    meta.write_text(
        json.dumps({"baseline_commit": baseline_commit}, indent=2),
        encoding="utf-8",
    )


def remote_exists(repo_path: Path, remote_name: str) -> bool:
    rc, out, err = _run_git(repo_path, ["remote"])
    if rc != 0:
        raise RuntimeError(f"git remote failed: {err or out}")
    remotes = out.splitlines() if out else []
    return remote_name in remotes


def add_or_set_remote(repo_path: Path, remote_name: str, repo_url: str) -> None:
    if remote_exists(repo_path, remote_name):
        # keep it updated in case URL changes
        rc, out, err = _run_git(repo_path, ["remote", "set-url", remote_name, repo_url])
        if rc != 0:
            raise RuntimeError(f"git remote set-url failed: {err or out}")
    else:
        rc, out, err = _run_git(repo_path, ["remote", "add", remote_name, repo_url])
        if rc != 0:
            raise RuntimeError(f"git remote add failed: {err or out}")


def fetch_remote(repo_path: Path, remote_name: str) -> str:
    # Fetch all refs from remote; return remote HEAD if possible (best-effort)
    rc, out, err = _run_git(repo_path, ["fetch", "--prune", remote_name])
    if rc != 0:
        raise RuntimeError(f"git fetch failed: {err or out}")

    # Best-effort: return current HEAD
    rc2, head, err2 = _run_git(repo_path, ["rev-parse", "HEAD"])
    if rc2 != 0:
        return ""
    return head


def get_ref(repo_path: Path, ref: str) -> str:
    rc, out, err = _run_git(repo_path, ["rev-parse", ref])
    if rc != 0:
        raise RuntimeError(f"git rev-parse {ref} failed: {err or out}")
    return out


def ahead_behind(repo_path: Path, left_ref: str, right_ref: str) -> Dict[str, int]:
    """
    Returns counts: how many commits left is ahead of right, and behind.
    Uses: git rev-list --left-right --count left...right
    """
    rc, out, err = _run_git(repo_path, ["rev-list", "--left-right", "--count", f"{left_ref}...{right_ref}"])
    if rc != 0:
        raise RuntimeError(f"git rev-list failed: {err or out}")
    # output: "<left_count>\t<right_count>"
    parts = out.replace("\t", " ").split()
    left = int(parts[0]) if len(parts) > 0 else 0
    right = int(parts[1]) if len(parts) > 1 else 0
    return {"ahead": left, "behind": right}


def diff_name_only(repo_path: Path, from_ref: str, to_ref: str) -> list[str]:
    rc, out, err = _run_git(repo_path, ["diff", "--name-only", f"{from_ref}..{to_ref}"])
    if rc != 0:
        raise RuntimeError(f"git diff --name-only failed: {err or out}")
    return out.splitlines() if out else []


def diff_name_only_scoped(repo_path: Path, from_ref: str, to_ref: str, paths: Optional[List[str]] = None) -> list[str]:
    """
    Scoped name-only diff: git diff --name-only from..to -- <paths...>
    """
    paths = [p for p in (paths or []) if p]
    args = ["diff", "--name-only", f"{from_ref}..{to_ref}"]
    if paths:
        args += ["--", *paths]
    rc, out, err = _run_git(repo_path, args)
    if rc != 0:
        raise RuntimeError(f"git diff --name-only (scoped) failed: {err or out}")
    return out.splitlines() if out else []


def read_upstream(repo_path: Path) -> Optional[Dict[str, Any]]:
    meta = repo_path / ".copilot" / "upstream.json"
    if not meta.exists():
        return None
    try:
        return json.loads(meta.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_upstream(repo_path: Path, data: Dict[str, Any]) -> None:
    meta_dir = repo_path / ".copilot"
    meta_dir.mkdir(parents=True, exist_ok=True)
    meta = meta_dir / "upstream.json"
    meta.write_text(json.dumps(data, indent=2), encoding="utf-8")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def diff_name_status_scoped(repo_path: Path, from_ref: str, to_ref: str, paths: Optional[List[str]] = None) -> List[Dict[str, str]]:
    """
    Scoped name/status diff: git diff --name-status from..to -- <paths...>
    Returns: [{"status": "A|M|D", "path": "..."}, ...]
    """
    paths = [p for p in (paths or []) if p]
    args = ["diff", "--name-status", f"{from_ref}..{to_ref}"]
    if paths:
        args += ["--", *paths]
    rc, out, err = _run_git(repo_path, args)
    if rc != 0:
        raise RuntimeError(f"git diff --name-status (scoped) failed: {err or out}")

    items: List[Dict[str, str]] = []
    for line in (out.splitlines() if out else []):
        # format: "M\tpath" or "A\tpath" or "D\tpath"
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        status, path = parts[0].strip(), parts[1].strip()
        if not status or not path:
            continue
        items.append({"status": status, "path": path})
    return items


def show_file_at_ref(repo_path: Path, ref: Optional[str], file_path: str) -> Optional[str]:
    """
    Returns file contents for ref:file_path using git show.
    If ref is None OR file doesn't exist at ref, returns None.
    """
    if not ref:
        return None
    rc, out, err = _run_git(repo_path, ["show", f"{ref}:{file_path}"])
    if rc != 0:
        return None
    return out if out is not None else ""
