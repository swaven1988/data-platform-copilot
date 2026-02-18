from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.git_ops.repo_manager import add_or_set_remote, fetch_remote, get_ref, ahead_behind, _run_git


def _copilot_dir(repo_path: Path) -> Path:
    d = repo_path / ".copilot"
    d.mkdir(parents=True, exist_ok=True)
    return d


def read_remotes(repo_path: Path) -> Dict[str, Any]:
    p = _copilot_dir(repo_path) / "remotes.json"
    if not p.exists():
        return {"remotes": {}}
    return json.loads(p.read_text(encoding="utf-8"))


def write_remotes(repo_path: Path, data: Dict[str, Any]) -> None:
    p = _copilot_dir(repo_path) / "remotes.json"
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")


def add_remote(repo_path: Path, *, name: str, url: str) -> Dict[str, Any]:
    if not name or not url:
        raise ValueError("name and url are required")
    add_or_set_remote(repo_path, name=name, url=url)
    data = read_remotes(repo_path)
    data.setdefault("remotes", {})
    data["remotes"][name] = {"url": url}
    write_remotes(repo_path, data)
    return data


def list_remotes(repo_path: Path) -> Dict[str, Any]:
    data = read_remotes(repo_path)
    # also include git-config remotes (best effort)
    rc, out, err = _run_git(repo_path, ["remote", "-v"])
    if rc == 0 and out:
        seen = set(data.get("remotes", {}).keys())
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                rname, rurl = parts[0], parts[1]
                if rname not in seen:
                    data.setdefault("remotes", {})[rname] = {"url": rurl}
                    seen.add(rname)
    return data


def fetch(repo_path: Path, *, name: str) -> Dict[str, Any]:
    fetch_remote(repo_path, name=name)
    return {"fetched": name}


def status(repo_path: Path, *, name: str, branch: str = "main") -> Dict[str, Any]:
    # Compare HEAD to <remote>/<branch>
    remote_ref = f"{name}/{branch}"
    head = get_ref(repo_path, "HEAD")
    remote_head = get_ref(repo_path, remote_ref)
    ab = ahead_behind(repo_path, head, remote_head)
    return {
        "remote": name,
        "branch": branch,
        "head": head,
        "remote_ref": remote_ref,
        "remote_head": remote_head,
        "ahead_behind": ab,
    }
