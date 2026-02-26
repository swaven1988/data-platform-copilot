# app/core/sync/guardrails.py

import hashlib
import json
import subprocess
from pathlib import Path


class SyncGuardError(Exception):
    pass


def get_head_commit(repo_path: Path) -> str:
    return (
        subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_path
        )
        .decode()
        .strip()
    )


def is_workspace_dirty(repo_path: Path) -> bool:
    status = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=repo_path
    ).decode()
    return bool(status.strip())


def validate_clean_workspace(repo_path: Path):
    if is_workspace_dirty(repo_path):
        raise SyncGuardError("Workspace dirty. Apply blocked.")


def validate_baseline(repo_path: Path, expected_commit: str):
    current = get_head_commit(repo_path)
    if current != expected_commit:
        raise SyncGuardError(
            f"HEAD drift detected. Expected {expected_commit}, found {current}"
        )


def compute_contract_hash(payload: dict) -> str:
    blob = json.dumps(payload, sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()