# PATCH 1 — app/core/federation/federation_manager.py
# Fix: cache repo may already exist with old origin URL (from previous test run).
# Solution: normalize URL + if cache exists, force-set origin URL to current spec.url before fetch.

# FIND: def sync_repo(...):
# REPLACE the whole function sync_repo() with this version.

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class FederatedRepoSpec:
    name: str
    url: str
    ref: str = "main"
    subdir: Optional[str] = None
    paths: Optional[List[str]] = None


class FederationError(RuntimeError):
    pass


def _run_git(args: List[str], cwd: Optional[Path] = None) -> str:
    try:
        p = subprocess.run(
            ["git", *args],
            cwd=str(cwd) if cwd else None,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return (p.stdout or "").strip()
    except FileNotFoundError as e:
        raise FederationError("git is not installed or not available on PATH") from e
    except subprocess.CalledProcessError as e:
        raise FederationError((e.stderr or e.stdout or str(e)).strip()) from e


def federation_dir(workspace_root: Path, job_name: str) -> Path:
    return workspace_root / job_name / ".copilot" / "federation"


def federation_config_path(workspace_root: Path, job_name: str) -> Path:
    return federation_dir(workspace_root, job_name) / "federation.json"


def _ensure_dirs(workspace_root: Path, job_name: str) -> None:
    d = federation_dir(workspace_root, job_name)
    d.mkdir(parents=True, exist_ok=True)


def load_federation_config(workspace_root: Path, job_name: str) -> Dict[str, Any]:
    _ensure_dirs(workspace_root, job_name)
    p = federation_config_path(workspace_root, job_name)
    if not p.exists():
        return {"kind": "federation_config", "repos": []}
    return json.loads(p.read_text(encoding="utf-8"))


def save_federation_config(workspace_root: Path, job_name: str, cfg: Dict[str, Any]) -> None:
    _ensure_dirs(workspace_root, job_name)
    p = federation_config_path(workspace_root, job_name)
    p.write_text(json.dumps(cfg, indent=2, sort_keys=True), encoding="utf-8")


def upsert_repo(workspace_root: Path, job_name: str, spec: FederatedRepoSpec) -> Dict[str, Any]:
    cfg = load_federation_config(workspace_root, job_name)
    repos = cfg.get("repos", [])
    new_repos = []
    replaced = False
    for r in repos:
        if r.get("name") == spec.name:
            new_repos.append(asdict(spec))
            replaced = True
        else:
            new_repos.append(r)
    if not replaced:
        new_repos.append(asdict(spec))
    cfg["repos"] = sorted(new_repos, key=lambda x: x.get("name", ""))
    save_federation_config(workspace_root, job_name, cfg)
    return cfg


def _repo_cache_dir(workspace_root: Path, job_name: str, repo_name: str) -> Path:
    return federation_dir(workspace_root, job_name) / "_git_cache" / repo_name


def _materialized_dir(workspace_root: Path, job_name: str, repo_name: str) -> Path:
    return federation_dir(workspace_root, job_name) / "materialized" / repo_name


def _clean_dir(p: Path) -> None:
    if p.exists():
        shutil.rmtree(p)
    p.mkdir(parents=True, exist_ok=True)


def _copy_selected(src_root: Path, dst_root: Path, *, subdir: Optional[str], paths: Optional[List[str]]) -> None:
    if subdir:
        s = src_root / subdir
        if not s.exists():
            raise FederationError(f"subdir not found in repo checkout: {subdir}")
        shutil.copytree(s, dst_root, dirs_exist_ok=True)
        return

    if paths:
        for rel in paths:
            s = src_root / rel
            if not s.exists():
                raise FederationError(f"path not found in repo checkout: {rel}")
            d = dst_root / rel
            d.parent.mkdir(parents=True, exist_ok=True)
            if s.is_dir():
                shutil.copytree(s, d, dirs_exist_ok=True)
            else:
                shutil.copy2(s, d)
        return

    shutil.copytree(src_root, dst_root, dirs_exist_ok=True)


def _normalize_git_url(url: str) -> str:
    # If it's a local path, use file:// URL for Windows reliability.
    try:
        p = Path(url)
        if p.exists():
            return p.resolve().as_uri()
    except Exception:
        pass
    return url


def sync_repo(workspace_root: Path, job_name: str, spec: FederatedRepoSpec) -> Dict[str, Any]:
    _ensure_dirs(workspace_root, job_name)

    cache = _repo_cache_dir(workspace_root, job_name, spec.name)
    materialized = _materialized_dir(workspace_root, job_name, spec.name)

    url = _normalize_git_url(spec.url)

    # internal engine only
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        _run_git(["clone", "--no-checkout", "--filter=blob:none", url, str(cache)])
    else:
        # IMPORTANT: cache may have an old origin URL (e.g., from a prior test run).
        # Force origin to current url, then fetch.
        try:
            _run_git(["remote", "set-url", "origin", url], cwd=cache)
        except FederationError:
            # if origin is missing for some reason, add it back
            _run_git(["remote", "add", "origin", url], cwd=cache)
        _run_git(["fetch", "--all", "--prune"], cwd=cache)

    # checkout into a temp workdir via worktree
    tmp = federation_dir(workspace_root, job_name) / "_tmp_checkout" / spec.name
    _clean_dir(tmp)

    _run_git(["worktree", "add", "--force", str(tmp), spec.ref], cwd=cache)

    _clean_dir(materialized)
    _copy_selected(tmp, materialized, subdir=spec.subdir, paths=spec.paths)

    head = _run_git(["rev-parse", "HEAD"], cwd=tmp)

    _run_git(["worktree", "remove", "--force", str(tmp)], cwd=cache)
    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)

    return {
        "name": spec.name,
        "url": spec.url,
        "ref": spec.ref,
        "head": head,
        "materialized_dir": str(materialized),
    }


def sync_all(workspace_root: Path, job_name: str) -> Dict[str, Any]:
    cfg = load_federation_config(workspace_root, job_name)
    results = []
    for r in cfg.get("repos", []):
        spec = FederatedRepoSpec(
            name=r["name"],
            url=r["url"],
            ref=r.get("ref", "main"),
            subdir=r.get("subdir"),
            paths=r.get("paths"),
        )
        results.append(sync_repo(workspace_root, job_name, spec))
    return {"job_name": job_name, "synced": results}
