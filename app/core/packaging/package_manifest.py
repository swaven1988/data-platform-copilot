from __future__ import annotations

import fnmatch
import hashlib
import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional


DEFAULT_INCLUDE_PATHS = [
    "app",
    "tests",
    "ui",
    "templates",
    "docs",
    ".github",
    "pyproject.toml",
    "README.md",
    "Makefile",
    "test.sh",
    "copilot_spec.yaml",
    "project_tree.txt",
    "project_file_paths.txt",
]

DEFAULT_EXCLUDES = [
    "**/__pycache__/**",
    "**/*.pyc",
    "**/.pytest_cache/**",
    "**/.mypy_cache/**",
    "**/.ruff_cache/**",
    "**/.venv/**",
    "**/workspace/**",
    "**/*.log",
    "**/*.tar.gz",
]


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def matches_any(path_posix: str, patterns: Iterable[str]) -> bool:
    for pat in patterns:
        if fnmatch.fnmatch(path_posix, pat):
            return True
    return False


def iter_included_files(project_root: Path, include_paths: List[str], excludes: List[str]) -> List[Path]:
    files: List[Path] = []

    for inc in include_paths:
        p = project_root / inc
        if not p.exists():
            continue

        if p.is_file():
            rel = p.relative_to(project_root).as_posix()
            if not matches_any(rel, excludes):
                files.append(p)
            continue

        for f in p.rglob("*"):
            if not f.is_file():
                continue
            rel = f.relative_to(project_root).as_posix()
            if matches_any(rel, excludes):
                continue
            files.append(f)

    uniq: Dict[str, Path] = {}
    for f in files:
        rel = f.relative_to(project_root).as_posix()
        uniq[rel] = f

    return [uniq[k] for k in sorted(uniq.keys())]


def generate_packaging_manifest(
    *,
    project_root: Path,
    include_paths: Optional[List[str]] = None,
    excludes: Optional[List[str]] = None,
) -> Dict:
    include_paths = include_paths or list(DEFAULT_INCLUDE_PATHS)
    excludes = excludes or list(DEFAULT_EXCLUDES)

    files = iter_included_files(project_root, include_paths, excludes)

    out_files: List[Dict[str, str]] = []
    for f in files:
        rel = f.relative_to(project_root).as_posix()
        out_files.append({"path": rel, "sha256": sha256_file(f)})

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


def manifests_equal(a: Dict, b: Dict) -> bool:
    return a == b
