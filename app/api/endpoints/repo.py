from pathlib import Path
from fastapi import APIRouter, HTTPException, Query

from app.core.git_ops.repo_manager import (
    git_status, read_baseline, diff,
    add_or_set_remote, fetch_remote, get_ref, ahead_behind,
    diff_name_only_scoped, diff_scoped,
    read_upstream, write_upstream, now_utc_iso
)

router = APIRouter(prefix="/repo", tags=["Repo"])

PROJECT_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_ROOT = PROJECT_ROOT / "workspace"

def _parse_paths(paths: str) -> list[str]:
    include = [p.strip() for p in (paths or "").split(",") if p.strip()]
    # Always exclude metadata folder from upstream drift/diff
    include = [p for p in include if p != ".copilot" and not p.startswith(".copilot")]
    return include


@router.get("/status")
def repo_status(job_name: str = Query(...)):
    try:
        repo_dir = WORKSPACE_ROOT / job_name
        if not repo_dir.exists():
            raise FileNotFoundError(f"Workspace repo not found: {repo_dir}")

        baseline = read_baseline(repo_dir)
        status = git_status(repo_dir)

        return {
            "job_name": job_name,
            "repo_dir": str(repo_dir),
            "baseline_commit": baseline,
            "status": status,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/diff")
def repo_diff(job_name: str = Query(...)):
    try:
        repo_dir = WORKSPACE_ROOT / job_name
        if not repo_dir.exists():
            raise FileNotFoundError(f"Workspace repo not found: {repo_dir}")

        baseline = read_baseline(repo_dir)
        if not baseline:
            return {"job_name": job_name, "diff": "", "note": "No baseline set yet."}

        d = diff(repo_dir, baseline, "HEAD")
        return {"job_name": job_name, "baseline_commit": baseline, "diff": d}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/upstream/connect")
def upstream_connect(job_name: str = Query(...), repo_url: str = Query(...), branch: str = Query("main")):
    """
    Attach upstream remote + persist config (per workspace job).
    """
    try:
        repo_dir = WORKSPACE_ROOT / job_name
        if not repo_dir.exists():
            raise FileNotFoundError(f"Workspace repo not found: {repo_dir}")

        remote_name = "upstream"
        add_or_set_remote(repo_dir, remote_name, repo_url)

        cfg = {
            "remote": remote_name,
            "repo_url": repo_url,
            "branch": branch,
            "connected_at": now_utc_iso(),
        }
        write_upstream(repo_dir, cfg)

        return {"job_name": job_name, "upstream": cfg, "note": "Upstream connected. Run /repo/upstream/fetch next."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/upstream/fetch")
def upstream_fetch(job_name: str = Query(...)):
    """
    Fetch upstream refs based on saved upstream.json.
    """
    try:
        repo_dir = WORKSPACE_ROOT / job_name
        if not repo_dir.exists():
            raise FileNotFoundError(f"Workspace repo not found: {repo_dir}")

        cfg = read_upstream(repo_dir)
        if not cfg:
            raise ValueError("No upstream config found. Call /repo/upstream/connect first.")

        remote = cfg.get("remote", "upstream")
        _ = fetch_remote(repo_dir, remote)

        cfg["last_fetch_at"] = now_utc_iso()

        branch = cfg.get("branch", "main")
        remote_ref = f"{remote}/{branch}"
        try:
            cfg["remote_ref"] = remote_ref
            cfg["remote_ref_commit"] = get_ref(repo_dir, remote_ref)
        except Exception:
            pass

        write_upstream(repo_dir, cfg)
        return {"job_name": job_name, "upstream": cfg}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/upstream/status")
def upstream_status(
    job_name: str = Query(...),
    paths: str = Query("jobs,dags,configs", description="Comma-separated path prefixes to include (e.g., app,ui,copilot_spec.yaml)"),
):
    """
    Show ahead/behind vs upstream branch + file drift summary.
    """
    try:
        repo_dir = WORKSPACE_ROOT / job_name
        if not repo_dir.exists():
            raise FileNotFoundError(f"Workspace repo not found: {repo_dir}")

        cfg = read_upstream(repo_dir)
        if not cfg:
            return {
                "job_name": job_name,
                "note": "No upstream config found. Call /repo/upstream/connect first.",
                "upstream": None,
            }

        if not cfg.get("last_fetch_at"):
            return {
                "job_name": job_name,
                "note": "Upstream connected but not fetched yet. Call /repo/upstream/fetch first.",
                "upstream": cfg,
            }

        remote = cfg.get("remote", "upstream")
        branch = cfg.get("branch", "main")
        remote_ref = cfg.get("remote_ref", f"{remote}/{branch}")

        head = get_ref(repo_dir, "HEAD")
        try:
            remote_head = get_ref(repo_dir, remote_ref)
        except Exception:
            return {
                "job_name": job_name,
                "note": f"Upstream ref not available locally ({remote_ref}). Run /repo/upstream/fetch again.",
                "workspace_head": head,
                "upstream_ref": remote_ref,
                "upstream": cfg,
            }

        ab = ahead_behind(repo_dir, "HEAD", remote_ref)
        include = _parse_paths(paths)
        changed_vs_upstream = diff_name_only_scoped(repo_dir, remote_ref, "HEAD", paths=include)
        changed_vs_upstream = [f for f in changed_vs_upstream if not f.startswith(".copilot/")]

        return {
            "job_name": job_name,
            "workspace_head": head,
            "upstream_ref": remote_ref,
            "upstream_head": remote_head,
            "ahead_behind": ab,
            "files_changed_vs_upstream": changed_vs_upstream,
            "upstream": cfg,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/upstream/diff")
def upstream_diff(
    job_name: str = Query(...),
    paths: str = Query("jobs,dags,configs", description="Comma-separated path prefixes to include"),
    direction: str = Query("upstream_to_workspace"),
    max_chars: int = Query(20000, ge=1000, le=500000),
):
    """
    direction:
      - upstream_to_workspace: git diff upstream_ref..HEAD
      - workspace_to_upstream: git diff HEAD..upstream_ref
    paths:
      - comma-separated scope prefixes, e.g. jobs,dags,configs
      - .copilot is always excluded
    """
    try:
        repo_dir = WORKSPACE_ROOT / job_name
        if not repo_dir.exists():
            raise FileNotFoundError(f"Workspace repo not found: {repo_dir}")

        cfg = read_upstream(repo_dir)
        if not cfg:
            return {"job_name": job_name, "diff": "", "note": "No upstream config found. Call /repo/upstream/connect first."}

        if not cfg.get("last_fetch_at"):
            return {"job_name": job_name, "diff": "", "note": "Upstream connected but not fetched yet. Call /repo/upstream/fetch first."}

        remote = cfg.get("remote", "upstream")
        branch = cfg.get("branch", "main")
        upstream_ref = cfg.get("remote_ref", f"{remote}/{branch}")

        include = _parse_paths(paths)

        if direction == "workspace_to_upstream":
            d = diff_scoped(repo_dir, "HEAD", upstream_ref, paths=include)
        else:
            d = diff_scoped(repo_dir, upstream_ref, "HEAD", paths=include)

        truncated = False
        original_len = len(d or "")
        if d and len(d) > max_chars:
            d = d[:max_chars] + "\n\n... (truncated) ..."
            truncated = True

        return {
            "job_name": job_name,
            "upstream_ref": upstream_ref,
            "direction": direction,
            "paths": include,
            "diff": d,
            "diff_truncated": truncated,
            "max_chars": max_chars,
            "diff_len": original_len,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

