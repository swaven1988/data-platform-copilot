from __future__ import annotations

import fnmatch
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List



DEFAULT_INCLUDE_PATHS: List[str] = [
    "app",
    "tests",
    "ui",
    "templates",
    "docs",
    ".github",
    "deploy",
    "tools",
    "README.md",
    "Makefile",
    "packaging_manifest.json",
    "project_tree.txt",
    "project_file_paths.txt",
]

DEFAULT_EXCLUDES: List[str] = [
    "**/__pycache__/**",
    "**/*.pyc",
    "**/.pytest_cache/**",
    "**/.mypy_cache/**",
    "**/.ruff_cache/**",
    "**/.venv/**",
    "**/.git/**",
    "**/.idea/**",
    "**/.vscode/**",
    "**/*.log",
    "**/.DS_Store",
    "**/node_modules/**",
    "**/dist/**",
    "**/build/**",
    "**/*.egg-info/**",
    "**/.copilot/**",
    "**/.pytest_cache/**",
]


def _matches_any(path: str, patterns: List[str]) -> bool:
    for pat in patterns:
        if fnmatch.fnmatch(path, pat):
            return True
    return False


def iter_included_files(
    *,
    project_root: Path,
    include_paths: List[str],
    excludes: List[str],
) -> Iterable[Path]:
    for rel in include_paths:
        p = (project_root / rel).resolve()
        if not p.exists():
            continue

        if p.is_file():
            rel_posix = p.relative_to(project_root).as_posix()
            if not _matches_any(rel_posix, excludes):
                yield p
            continue

        for f in p.rglob("*"):
            if not f.is_file():
                continue
            rel_posix = f.relative_to(project_root).as_posix()
            if _matches_any(rel_posix, excludes):
                continue
            yield f


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def generate_packaging_manifest(
    *,
    project_root: Path,
    include_paths: List[str] | None = None,
    excludes: List[str] | None = None,
) -> Dict:
    include_paths = list(include_paths or DEFAULT_INCLUDE_PATHS)
    excludes = list(excludes or DEFAULT_EXCLUDES)

    # normalize ordering for determinism
    include_paths = sorted(dict.fromkeys(include_paths))
    excludes = sorted(dict.fromkeys(excludes))

    out_files = []
    for f in sorted(
        iter_included_files(project_root=project_root, include_paths=include_paths, excludes=excludes),
        key=lambda p: p.relative_to(project_root).as_posix(),
    ):
        rel = f.relative_to(project_root).as_posix()

        # ---- Canonical hashing: use git index blob to avoid Windows CRLF drift ----
        blob = None
        try:
            # ":" means "from index" (not working tree). This is stable across OS/autocrlf.
            blob = subprocess.check_output(
                ["git", "-C", str(project_root), "show", f":{rel}"],
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            blob = None

        if blob is not None:
            sha = hashlib.sha256(blob).hexdigest()
            size = len(blob)
        else:
            sha = sha256_file(f)
            size = f.stat().st_size
        
        out_files.append(
            {
                "path": rel,
                "sha256": sha,
                "size": size,

            }
        )

    return {
        "kind": "packaging_manifest",
        "include_paths": include_paths,
        "excludes": excludes,
        "files": out_files,
    }


def write_manifest(path: Path, manifest: Dict) -> None:
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


def load_manifest(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_manifest(m: Dict) -> Dict:
    m2 = dict(m or {})
    m2["kind"] = m2.get("kind")

    inc = list(m2.get("include_paths") or [])
    exc = list(m2.get("excludes") or [])
    m2["include_paths"] = sorted(dict.fromkeys(inc))
    m2["excludes"] = sorted(dict.fromkeys(exc))

    files = list(m2.get("files") or [])
    norm_files = []
    for e in files:
        if not isinstance(e, dict):
            continue
        path = e.get("path")
        if not path:
            continue
        norm_files.append(
            {
                "path": str(path),
                "sha256": e.get("sha256"),
                "size": e.get("size"),
            }
        )
    norm_files.sort(key=lambda x: x["path"])
    m2["files"] = norm_files
    return m2


def manifests_equal(a: Dict, b: Dict) -> bool:
    """
    Manifest comparison that is deterministic across OS/filesystems.

    IMPORTANT:
    - Ignore packaging_manifest.json inside the 'files' list.
      That file is the snapshot itself and will legitimately change when rewritten.
    """

    def _norm_files(m: Dict) -> Dict[str, Dict]:
        out: Dict[str, Dict] = {}
        for e in (m.get("files") or []):
            if not isinstance(e, dict):
                continue
            p = e.get("path")
            if not p:
                continue

            # Ignore self-reference to avoid recursive self-hash mismatch
            if p.replace("\\", "/") == "packaging_manifest.json":
                continue

            # Keep only stable fields (some builds may include size)
            out[p] = {
                "path": p,
                "sha256": e.get("sha256"),
                "size": e.get("size"),
            }
        return out

    # Compare top-level stable fields first
    if (a.get("kind") != b.get("kind")):
        return False
    if (a.get("include_paths") != b.get("include_paths")):
        return False
    if (a.get("excludes") != b.get("excludes")):
        return False

    A = _norm_files(a)
    B = _norm_files(b)

    if set(A.keys()) != set(B.keys()):
        return False

    for p in A.keys():
        # Compare sha always; compare size only if both sides have it
        if A[p].get("sha256") != B[p].get("sha256"):
            return False
        sa, sb = A[p].get("size"), B[p].get("size")
        if sa is not None and sb is not None and sa != sb:
            return False

    return True