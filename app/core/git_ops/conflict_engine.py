from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Tuple

from app.core.git_ops.repo_manager import _run_git


@dataclass(frozen=True)
class ConflictFile:
    path: str
    markers: int


def _count_conflict_markers(text: str) -> int:
    if not text:
        return 0
    return sum(text.count(x) for x in ("<<<<<<<", "=======", ">>>>>>>"))


def detect_conflicts(repo_path: Path) -> Dict[str, Any]:
    """Detect merge/rebase conflicts and conflict markers in working tree files."""
    git_dir = repo_path / ".git"
    in_merge = (git_dir / "MERGE_HEAD").exists()
    in_rebase = (git_dir / "rebase-apply").exists() or (git_dir / "rebase-merge").exists()

    rc, out, err = _run_git(repo_path, ["status", "--porcelain"])
    if rc != 0:
        raise RuntimeError(err or out)

    conflicted: List[str] = []
    for line in (out.splitlines() if out else []):
        # porcelain: XY <path>
        if len(line) >= 3:
            xy = line[:2]
            p = line[3:].strip()
            if xy in ("UU", "AA", "DD", "AU", "UA", "DU", "UD"):
                conflicted.append(p)

    files: List[ConflictFile] = []
    for p in sorted(set(conflicted)):
        fp = repo_path / p
        try:
            text = fp.read_text(encoding="utf-8", errors="replace")
        except Exception:
            text = ""
        files.append(ConflictFile(path=p, markers=_count_conflict_markers(text)))

    return {
        "repo_path": str(repo_path),
        "in_merge": in_merge,
        "in_rebase": in_rebase,
        "conflicted_files": [f.__dict__ for f in files],
        "conflict_count": len(files),
    }


def conflict_help(repo_path: Path) -> Dict[str, Any]:
    state = detect_conflicts(repo_path)
    steps: List[str] = []
    if state["conflict_count"] == 0:
        steps.append("No conflicts detected.")
        return {"state": state, "steps": steps}

    if state["in_rebase"]:
        steps += [
            "You are in a rebase.",
            "1) Open each conflicted file and resolve conflict markers.",
            "2) git add <file> for each resolved file",
            "3) git rebase --continue",
            "If you want to abort: git rebase --abort",
        ]
    elif state["in_merge"]:
        steps += [
            "You are in a merge.",
            "1) Open each conflicted file and resolve conflict markers.",
            "2) git add <file> for each resolved file",
            "3) git commit (or complete the merge via your tooling)",
            "If you want to abort: git merge --abort",
        ]
    else:
        steps += [
            "Conflicted files detected but repo is not in merge/rebase state.",
            "Resolve files and then stage them: git add <file>",
        ]
    return {"state": state, "steps": steps}
